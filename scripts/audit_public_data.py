"""Audit published files for five seasons. Never scrapes protected source websites."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '8940299c2c56c2c0932d3caf292336f5e1689893'
TOP5_URL = f'https://raw.githubusercontent.com/m-mahadi/top5-football-dataset/{COMMIT}/data/master/player_seasons.csv'
TM_BASE = 'https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/'
LEAGUES = {'ENG-Premier League': ('GB1', 20), 'ESP-La Liga': ('ES1', 20),
           'ITA-Serie A': ('IT1', 20), 'GER-Bundesliga': ('L1', 18),
           'FRA-Ligue 1': ('FR1', 20)}
SEASONS = range(2021, 2026)
NULLS = {'', 'nan', 'none', 'null', 'na', 'n/a'}


def number(value):
    if value is None or str(value).strip().lower() in NULLS:
        return None
    try:
        result = float(value)
        if result != result or abs(result) == float('inf'):
            return None
        return result
    except (TypeError, ValueError):
        return None


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def download(url, path):
    """Cache published files, no retries/proxies/browser tricks on a denial."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return {'status': 'cached', 'sha256': digest(path), 'path': str(path), 'url': url}
    tmp = path.with_suffix(path.suffix + '.part')
    try:
        with urlopen(url, timeout=30) as response, tmp.open('wb') as stream:
            total = 0
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                total += len(chunk)
                if total > 512 * 1024 * 1024:
                    raise ValueError('File exceeds 512 MiB download cap.')
                stream.write(chunk)
        tmp.replace(path)
        return {'status': 'downloaded', 'sha256': digest(path), 'path': str(path), 'url': url,
                'retrieved_at': datetime.now(timezone.utc).isoformat()}
    except HTTPError as exc:
        return {'status': 'blocked' if exc.code in (401, 403, 429) else 'failed',
                'http_status': exc.code, 'url': url}
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        return {'status': 'failed', 'error_type': type(exc).__name__, 'url': url}
    finally:
        tmp.unlink(missing_ok=True)


def read_csv(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError('CSV has no header.')
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError('CSV has an inconsistent row width.')
            yield row


def expected(league, year):
    teams = 18 if league == 'FRA-Ligue 1' and year >= 2023 else LEAGUES[league][1]
    return teams, teams * (teams - 1)


def base_matrix():
    return {(league, year): {'league': league, 'season': f'{year}/{str(year+1)[-2:]}',
                            'expected_teams': expected(league, year)[0],
                            'expected_league_matches': expected(league, year)[1],
                            'status': 'missing', 'rows': 0}
            for league in LEAGUES for year in SEASONS}


def audit_top5(rows):
    matrix = base_matrix()
    seen, teamsets = set(), defaultdict(set)
    duplicates, blanks, invalid, outscope = 0, 0, 0, 0
    fields = {'minutes': 'playing_time_min', 'appearances': 'playing_time_mp',
              'goals': 'fb_gls', 'assists': 'fb_ast', 'xg': 'us_xg'}
    missing, bad = defaultdict(Counter), defaultdict(Counter)
    cross = defaultdict(lambda: {'comparable': 0, 'different': 0,
                                'different_multi_club_rows': 0, 'max_abs_difference': 0})
    required = {'league', 'season_label', 'team', 'player', *fields.values()}
    for row in rows:
        if not required.issubset(row):
            raise ValueError('Top-five CSV is missing required columns.')
        try:
            year = int(row['season_label'].split('/')[0])
        except ValueError:
            raise ValueError('Invalid season label.') from None
        key = (row['league'], year)
        if key not in matrix:
            outscope += 1
            continue
        cell = matrix[key]
        cell['rows'] += 1
        identity = (row['league'], row['season_label'], row['team'], row['player'])
        duplicates += identity in seen
        seen.add(identity)
        blanks += any(not str(v).strip() for v in identity)
        if row['team']:
            teamsets[key].add(row['team'])
        for label, column in fields.items():
            value = number(row[column])
            if value is None:
                missing[key][label] += 1
                if str(row[column]).strip().lower() not in NULLS:
                    bad[key][label] += 1
                    invalid += 1
            elif value < 0:
                bad[key][label] += 1
                invalid += 1
        # Same metric label, but club/season scopes still need reconciliation.
        for label, left, right in [('goals_fb_vs_ss', 'fb_gls', 'ss_goals'),
                                    ('assists_fb_vs_ss', 'fb_ast', 'ss_assists')]:
            a, b = number(row.get(left)), number(row.get(right))
            if a is not None and b is not None:
                result = cross[label]
                result['comparable'] += 1
                result['different'] += abs(a-b) > 1e-9
                result['different_multi_club_rows'] += (
                    abs(a-b) > 1e-9 and str(row.get('multi_club', '')).lower() == 'true')
                result['max_abs_difference'] = max(result['max_abs_difference'], abs(a-b))
    for key, cell in matrix.items():
        if cell['rows']:
            cell.update(status='present_not_completeness_verified',
                        observed_team_labels=len(teamsets[key]),
                        missing_fields={field: missing[key][field] for field in fields},
                        invalid_fields=dict(bad[key]))
    return {'source': 'top5', 'source_commit': COMMIT, 'matrix': list(matrix.values()),
            'duplicate_name_keys': duplicates, 'blank_identity_rows': blanks,
            'invalid_numeric_values': invalid, 'out_of_scope_rows': outscope,
            'cross_source_counts': dict(cross),
            'limitations': ['Name keys are not verified player identities.',
                'Source metrics may refer to different club stints; discrepancies are flags, not proof of error.',
                'Season presence and team counts do not prove complete player coverage.',
                'Current SoFIFA values/attributes must not be used as historical prediction features.',
                'Underlying data permissions remain unresolved; not approved for public redistribution or ML.']}


def audit_transfermarkt(games, appearances):
    matrix = base_matrix()
    ids = {value[0]: name for name, value in LEAGUES.items()}
    game_map, teams, covered, players = {}, defaultdict(set), defaultdict(set), defaultdict(set)
    missing, duplicates, seen, orphan = defaultdict(Counter), 0, set(), 0
    for row in games:
        if not {'game_id','competition_id','season','date','home_club_id','away_club_id'}.issubset(row):
            raise ValueError('Games CSV missing required columns.')
        value = number(row['season'])
        if value is None or value != int(value):
            raise ValueError('Invalid game season.')
        key = (ids.get(row['competition_id']), int(value))
        gid = row['game_id']
        if not gid or gid in game_map:
            raise ValueError('Missing or duplicate game ID.')
        game_map[gid] = key
        if key not in matrix:
            continue
        cell = matrix[key]
        cell['rows'] += 1
        teams[key].update([row['home_club_id'],row['away_club_id']])
        date = row['date'][:10]
        datetime.strptime(date, '%Y-%m-%d')
        cell['first_match'] = min(cell.get('first_match', date), date)
        cell['last_match'] = max(cell.get('last_match', date), date)
    for row in appearances:
        if not {'game_id','player_id','player_club_id','minutes_played','goals','assists'}.issubset(row):
            raise ValueError('Appearances CSV missing required columns.')
        gid = row['game_id']
        if gid not in game_map:
            orphan += 1
            continue
        key = game_map[gid]
        if key not in matrix:
            continue
        identity = (gid, row['player_id'])
        duplicates += identity in seen
        seen.add(identity)
        covered[key].add(gid)
        players[key].add(row['player_id'])
        cell = matrix[key]
        cell['appearance_rows'] = cell.get('appearance_rows', 0) + 1
        for field in ['minutes_played','goals','assists']:
            value = number(row[field])
            if value is None:
                missing[key][field] += 1
            elif value < 0:
                raise ValueError('Negative appearance statistic.')
    for key, cell in matrix.items():
        if cell['rows']:
            cell.update(status='present_not_completeness_verified', observed_teams=len(teams[key]),
                        games_with_appearances=len(covered[key]), unique_player_ids=len(players[key]),
                        games_without_appearances=cell['rows']-len(covered[key]),
                        schedule_count_matches_expectation=cell['rows']==cell['expected_league_matches'],
                        missing_fields=dict(missing[key]))
    return {'source': 'transfermarkt', 'matrix': list(matrix.values()),
            'duplicate_player_game_keys': duplicates, 'orphan_appearance_rows': orphan,
            'limitations': ['Count agreement is not an independent match-list reconciliation.',
                           'No claim of full tournament or trophy coverage.',
                           'Historical club must come from player_club_id, not player_current_club_id.',
                           'Underlying publication rights are not established by repository CC0 alone.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=['top5','transfermarkt','all'], default='all')
    parser.add_argument('--offline', action='store_true', help='Only inspect files already downloaded')
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data/raw/public_audit')
    parser.add_argument('--output', type=Path, default=ROOT/'data/processed/public_audit/report.json')
    args = parser.parse_args()
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'sources': {}}
    sources = ['top5','transfermarkt'] if args.source == 'all' else [args.source]
    for source in sources:
        spec = {'player_seasons.csv': TOP5_URL} if source == 'top5' else {
            name: TM_BASE+name for name in ['games.csv.gz','appearances.csv.gz']}
        entries, usable = {}, True
        for name, url in spec.items():
            path = args.data_dir/source/name
            if args.offline:
                entry = ({'status':'local','sha256':digest(path),'path':str(path),'url':url}
                         if path.exists() else {'status':'missing','url':url})
            else:
                entry = download(url,path)
            entries[name] = entry
            print(f'{source}/{name}: {entry["status"]}', flush=True)
            if entry['status'] not in ('cached','downloaded','local'):
                usable = False
                break  # Stop this source on denied/failed access; do not circumvent.
        result = {'files':entries,'status':'unavailable','coverage':'unverified'}
        if usable:
            try:
                if source == 'top5':
                    path = args.data_dir/source/'player_seasons.csv'
                    # Verify the source Git blob, including offline/manual copies.
                    content = path.read_bytes()
                    blob = hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()
                    if blob != 'e7752ce810d3475808cbc2822bdcb6ead7ccf79e':
                        raise ValueError('Top-five file differs from pinned Git blob; do not mix snapshots.')
                    result['audit'] = audit_top5(read_csv(path))
                else:
                    result['audit'] = audit_transfermarkt(read_csv(args.data_dir/source/'games.csv.gz'),
                                                         read_csv(args.data_dir/source/'appearances.csv.gz'))
                result['status'] = 'audited'
            except (ValueError, OSError, EOFError, csv.Error) as exc:
                result.update(status='invalid', error=str(exc))
        report['sources'][source] = result
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix('.tmp')
    tmp.write_text(json.dumps(report,indent=2),encoding='utf-8')
    tmp.replace(args.output)
    print(f'Report: {args.output}')
    for source, result in report['sources'].items():
        if 'audit' in result:
            present = sum(cell['rows']>0 for cell in result['audit']['matrix'])
            print(f'{source}: {present}/25 league-season cells present; completeness unverified')
    return 0 if all(s['status']=='audited' for s in report['sources'].values()) else 1


if __name__ == '__main__':
    sys.exit(main())
