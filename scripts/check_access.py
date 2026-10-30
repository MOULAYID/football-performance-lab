"""Small read-only access audit. Python 3.10+, standard library only."""
import argparse
import getpass
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class AuditError(Exception):
    pass


def error_reason(payload, token):
    """Expose only error fields, redact the supplied credential before truncating."""
    if not isinstance(payload, dict):
        return 'Check credentials, subscription, or quota in the dashboard.'
    detail = payload.get('errors') or payload.get('message') or payload.get('errorCode')
    if not detail:
        return 'Check credentials, subscription, or quota in the dashboard.'
    text = json.dumps(detail, ensure_ascii=False)
    if token:
        for secret in (json.dumps(token, ensure_ascii=False)[1:-1], token):
            text = text.replace(secret, '[REDACTED]')
    return ''.join(c for c in text if c.isprintable())[:800]


def fetch(base, path, header, token, params=None):
    url = base + path
    if params:
        url += '?' + urlencode(params)
    request = Request(url, headers={header: token, 'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as exc:
        try:
            reason = error_reason(json.loads(exc.read(16384)), token)
        except (ValueError, UnicodeError, OSError):
            reason = 'Check credentials, subscription, or quota in the dashboard.'
        raise AuditError(f'{path}: HTTP {exc.code}: {reason}') from None
    except (URLError, TimeoutError, OSError):
        raise AuditError('Network request failed. Check connectivity and retry later.') from None
    except (ValueError, UnicodeError):
        raise AuditError('Provider returned an invalid JSON response.') from None
    if not isinstance(payload, dict):
        raise AuditError('Unexpected response structure.')
    if payload.get('errors') or payload.get('errorCode'):
        raise AuditError(f'{path}: {error_reason(payload, token)}')
    return payload


def summarize_players(payload, league, season):
    rows = payload.get('response', [])
    if not isinstance(rows, list):
        raise AuditError('Unexpected player response structure.')
    fields = {'minutes': ('games', 'minutes'), 'position': ('games', 'position'),
              'goals': ('goals', 'total'), 'assists': ('goals', 'assists')}
    missing = dict.fromkeys(fields, 0)
    count = 0
    ids = []
    for row in rows:
        ids.append(row.get('player', {}).get('id'))
        for stat in row.get('statistics', []):
            scope = stat.get('league', {})
            if scope.get('id') != league or scope.get('season') != season:
                continue
            count += 1
            for field, (section, key) in fields.items():
                if (stat.get(section) or {}).get(key) is None:
                    missing[field] += 1
    valid_ids = [value for value in ids if value is not None]
    return {'sample_only': True, 'player_records': len(rows),
            'missing_player_ids': len(ids) - len(valid_ids),
            'duplicate_player_ids': len(valid_ids) - len(set(valid_ids)),
            'matching_stat_rows': count, 'missing_fields': missing,
            'paging': payload.get('paging', {})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=['football-data', 'api-football'], required=True)
    parser.add_argument('--league', type=int, default=39, help='API-Football league ID; 39 = Premier League')
    parser.add_argument('--season', type=int, help='Optional season start year; requests ONE player page')
    args = parser.parse_args()
    env = 'FOOTBALL_DATA_TOKEN' if args.provider == 'football-data' else 'API_FOOTBALL_KEY'
    token = os.environ.get(env) or getpass.getpass(f'{env} (hidden input): ')
    if not token.strip():
        print('No credential provided; no requests made.')
        return 1
    try:
        if args.provider == 'football-data':
            if args.season is not None:
                raise AuditError('--season is only supported for the API-Football sample.')
            data = fetch('https://api.football-data.org/v4', '/competitions', 'X-Auth-Token', token)
            result = {'provider': args.provider, 'competitions': [
                {'code': c.get('code'), 'name': c.get('name'), 'plan': c.get('plan'),
                 'current_season': c.get('currentSeason')}
                for c in data.get('competitions', [])],
                'note': 'A competition listing does not prove access to all historical endpoints.'}
        else:
            base = 'https://v3.football.api-sports.io'
            data = fetch(base, '/leagues', 'x-apisports-key', token, {'id': args.league})
            result = {'provider': args.provider, 'league': args.league,
                      'seasons': [{'year': s.get('year'), 'start': s.get('start'),
                                   'end': s.get('end'), 'coverage': s.get('coverage')}
                                  for item in data.get('response', []) for s in item.get('seasons', [])],
                      'note': 'Coverage is advertised, not proof of subscription access or complete data.'}
            if args.season is not None:
                sample = fetch(base, '/players', 'x-apisports-key', token,
                               {'league': args.league, 'season': args.season, 'page': 1})
                result['player_sample'] = summarize_players(sample, args.league, args.season)
        print(json.dumps(result, indent=2))
        return 0
    except AuditError as exc:
        print(f'Check failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
