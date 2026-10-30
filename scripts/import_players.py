"""Resume a local API-Football season download; validate before exporting CSV."""
import argparse
import csv
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import time

try:
    from .check_access import AuditError, fetch
except ImportError:
    from check_access import AuditError, fetch

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['player_id', 'player_name', 'team_id', 'team_name', 'league_id',
          'season', 'position', 'appearances', 'minutes', 'goals', 'assists']


def atomic_json(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    tmp.replace(path)


def validate_page(payload, page, total=None):
    if not isinstance(payload, dict) or payload.get('errors'):
        raise AuditError('Invalid or failed cached response.')
    paging = payload.get('paging', {})
    actual = paging.get('total')
    if (paging.get('current') != page or type(actual) is not int or actual < page
            or (total is not None and actual != total)):
        raise AuditError('Pagination changed or is invalid. Use a new --snapshot name to restart.')
    rows = payload.get('response')
    if not isinstance(rows, list) or not rows:
        raise AuditError('Empty or invalid player page; no complete export produced.')
    return actual


def normalize(pages, league, season):
    records = {}
    player_ids = set()
    duplicate_rows = 0
    player_records = 0
    for payload in pages:
        for item in payload['response']:
            player_records += 1
            player = item.get('player') or {}
            pid = player.get('id')
            if type(pid) is not int:
                raise AuditError('Player record has no integer ID.')
            if pid in player_ids:
                raise AuditError('Player repeated across pages; pagination may have shifted. Use a new snapshot.')
            player_ids.add(pid)
            matched = False
            for stat in item.get('statistics', []):
                scope = stat.get('league') or {}
                if scope.get('id') != league or scope.get('season') != season:
                    continue
                matched = True
                team = stat.get('team') or {}
                tid = team.get('id')
                if type(tid) is not int:
                    raise AuditError('Statistic row has no integer team ID.')
                games, goals = stat.get('games') or {}, stat.get('goals') or {}
                row = dict(zip(FIELDS, [pid, player.get('name'), tid, team.get('name'),
                    league, season, games.get('position'), games.get('appearences'),
                    games.get('minutes'), goals.get('total'), goals.get('assists')]))
                for field in ['appearances', 'minutes', 'goals', 'assists']:
                    value = row[field]
                    if value is not None and (type(value) is not int or value < 0):
                        raise AuditError(f'Invalid nonnegative integer in {field}.')
                key = (pid, tid, league, season)
                if key in records:
                    if records[key] != row:
                        raise AuditError('Conflicting statistics for a player/team/season.')
                    duplicate_rows += 1
                records[key] = row
            if not matched:
                raise AuditError('Player has no statistics for the requested league and season.')
    rows = [records[key] for key in sorted(records)]
    missing = {field: sum(r[field] is None for r in rows)
               for field in ['minutes', 'position', 'goals', 'assists']}
    report = {'league': league, 'season': season, 'pages': len(pages),
              'player_records': player_records, 'unique_players': len(player_ids),
              'statistic_rows': len(rows), 'identical_rows_deduplicated': duplicate_rows,
              'missing_fields': missing,
              'note': 'Nulls preserved. All API pages fetched; football coverage is not independently verified.'}
    return rows, report


def run(args):
    if args.max_requests < 1 or args.delay < 7:
        raise AuditError('Use --max-requests >= 1 and --delay >= 7 seconds.')
    if not args.snapshot or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.snapshot):
        raise AuditError('Snapshot name must contain only letters, numbers, hyphens, or underscores.')
    folder = ROOT / 'data' / 'raw' / f'api-football_{args.league}_{args.season}_{args.snapshot}'
    folder.mkdir(parents=True, exist_ok=True)
    pages, total, page, requests, token = [], None, 1, 0, None
    while total is None or page <= total:
        path = folder / f'page_{page:03d}.json'
        if path.exists():
            envelope = json.loads(path.read_text(encoding='utf-8'))
            if envelope.get('league') != args.league or envelope.get('season') != args.season:
                raise AuditError('Cached scope does not match request.')
            payload = envelope['payload']
        else:
            if requests >= args.max_requests:
                print(f'Paused after {requests} new requests; {len(pages)}/{total} pages cached. Rerun to resume.')
                return 0
            if token is None:
                token = (os.environ.get('API_FOOTBALL_KEY') or getpass.getpass('API_FOOTBALL_KEY (hidden input): ')).strip()
                if not token:
                    raise AuditError('No key supplied.')
            if requests:
                time.sleep(args.delay)
            payload = fetch('https://v3.football.api-sports.io', '/players', 'x-apisports-key', token,
                            {'league': args.league, 'season': args.season, 'page': page})
            requests += 1
            validate_page(payload, page, total)
            atomic_json(path, {'league': args.league, 'season': args.season,
                              'retrieved_at': datetime.now(timezone.utc).isoformat(),
                              'payload': payload})
        total = validate_page(payload, page, total)
        pages.append(payload)
        print(f'Validated page {page}/{total}', flush=True)
        page += 1
    rows, report = normalize(pages, args.league, args.season)
    out = ROOT / 'data' / 'processed' / folder.name
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'players.csv'
    tmp = target.with_suffix('.tmp')
    with tmp.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(target)
    report['completed_at'] = datetime.now(timezone.utc).isoformat()
    atomic_json(out / 'quality_report.json', report)
    print(json.dumps(report, indent=2))
    print(f'Local export: {target}')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--league', type=int, default=39)
    parser.add_argument('--season', type=int, default=2024)
    parser.add_argument('--snapshot', default='initial')
    parser.add_argument('--max-requests', type=int, default=35, help='New requests allowed in this run; not remaining daily quota')
    parser.add_argument('--delay', type=float, default=7, help='Seconds between new requests')
    args = parser.parse_args()
    try:
        return run(args)
    except (AuditError, OSError, ValueError, KeyError) as exc:
        # Unexpected data errors should not print raw provider content.
        print(f'Import stopped: {exc}' if isinstance(exc, AuditError)
              else 'Import stopped: local file or response format error. Cached pages were retained.')
        return 1
    except KeyboardInterrupt:
        print('\nStopped. Completed pages are cached; rerun to resume.')
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
