"""Build a local DuckDB warehouse from cached Kaggle files. Python 3.10+."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

try:
    from .audit_public_data import ROOT, KAGGLE_BASE, download, digest
except ImportError:
    from audit_public_data import ROOT, KAGGLE_BASE, download, digest

FILES = ('games','appearances','players','clubs','competitions')


def build_database(data_dir, output, *, memory_limit='1GB', threads=2):
    import duckdb
    data_dir, output = Path(data_dir), Path(output)
    for name in FILES:
        if not (data_dir/f'{name}.csv').is_file():
            raise ValueError(f'Missing {name}.csv; run with --download or provide --data-dir.')
    output.parent.mkdir(parents=True,exist_ok=True)
    # Build next to the destination; replace it only after validation and close.
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='build_') as tmp:
        pending = Path(tmp)/'football.duckdb'
        con = duckdb.connect(str(pending))
        try:
            con.execute("SET memory_limit = ?", [memory_limit])
            con.execute('SET threads = ?', [threads])
            for name in FILES:
                con.execute(f'CREATE TEMP TABLE raw_{name} AS SELECT * FROM read_csv(?, header=true, all_varchar=true)',
                            [str(data_dir/f'{name}.csv')])
            con.execute((ROOT/'sql/build_database.sql').read_text())
            checks = {
                'missing_player_references': 'SELECT COUNT(*) FROM player_match_stats a ANTI JOIN players p USING(player_id)',
                'missing_home_clubs': 'SELECT COUNT(*) FROM matches m ANTI JOIN clubs c ON m.home_club_id=c.club_id',
                'missing_away_clubs': 'SELECT COUNT(*) FROM matches m ANTI JOIN clubs c ON m.away_club_id=c.club_id',
                'missing_competitions': 'SELECT COUNT(*) FROM matches m ANTI JOIN competitions c USING(competition_id)',
                'wrong_historical_club': 'SELECT COUNT(*) FROM player_match_stats a JOIN matches m USING(game_id) WHERE a.club_id IS NULL OR a.club_id NOT IN (m.home_club_id,m.away_club_id)',
                'negative_statistics': 'SELECT COUNT(*) FROM player_match_stats WHERE minutes<0 OR goals<0 OR assists<0',
                'null_match_scope': 'SELECT COUNT(*) FROM matches WHERE match_date IS NULL OR home_club_id IS NULL OR away_club_id IS NULL',
            }
            results = {name:con.execute(query).fetchone()[0] for name,query in checks.items()}
            if any(results.values()):
                raise ValueError('Integrity checks failed: '+json.dumps(results))
            if con.execute('SELECT COUNT(*) FROM player_match_stats').fetchone()[0]==0:
                raise ValueError('No in-scope player statistics; database not replaced.')
            con.execute('CREATE TABLE source_files (file_name VARCHAR PRIMARY KEY, source_url VARCHAR, sha256 VARCHAR, loaded_at TIMESTAMPTZ)')
            now=datetime.now(timezone.utc)
            for name in FILES:
                con.execute('INSERT INTO source_files VALUES (?,?,?,?)',
                            [name+'.csv',KAGGLE_BASE+name+'.csv',digest(data_dir/f'{name}.csv'),now])
            counts={name:con.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
                    for name in ['matches','player_match_stats','players','clubs','competitions','player_club_season','player_season']}
            coverage=con.execute('SELECT * FROM league_season_coverage ORDER BY competition_id,season')
            cols=[d[0] for d in coverage.description]
            cells=[dict(zip(cols,r)) for r in coverage.fetchall()]
            missing=con.execute('SELECT game_id,competition_id,season,match_date FROM match_coverage WHERE missing_appearances ORDER BY game_id').fetchall()
            report={'built_at':now.isoformat(),'duckdb_version':duckdb.__version__,'counts':counts,
                    'integrity_checks':results,'coverage':cells,'missing_appearance_matches':[list(r) for r in missing],
                    'notes':['Position and club names are source snapshots, not historical position/name evidence.',
                             'Null metrics remain null; unrecorded matches are never treated as zero.',
                             'All totals are observed records, not guaranteed complete career or award-period totals.']}
            con.execute('CHECKPOINT')
        finally:
            con.close()
        pending.replace(output)
    report_path=output.with_suffix('.build.json')
    report_path.write_text(json.dumps(report,indent=2,default=str)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data/raw/public_audit/transfermarkt-kaggle')
    parser.add_argument('--output',type=Path,default=ROOT/'data/processed/football.duckdb')
    parser.add_argument('--download',action='store_true',help='Fetch missing published CSVs; reuse cached files')
    args=parser.parse_args()
    try:
        import duckdb
    except ImportError:
        print('Install dependencies first: python -m pip install -r requirements.txt')
        return 1
    try:
        if args.download:
            for name in FILES:
                result=download(KAGGLE_BASE+name+'.csv',args.data_dir/(name+'.csv'))
                print(name+': '+result['status'],flush=True)
                if result['status'] not in ('cached','downloaded'):
                    print('Download unavailable; stopped without replacing the database.')
                    return 1
        report=build_database(args.data_dir,args.output)
        print(json.dumps(report['counts'],indent=2))
        print('Matches missing appearances:',len(report['missing_appearance_matches']))
        print('Database:',args.output)
        print('Build report:',args.output.with_suffix('.build.json'))
        return 0
    except (ValueError,OSError,duckdb.Error) as exc:
        print('Build failed:',exc)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
