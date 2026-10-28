# Local analytical database

This milestone turns the audited Kaggle CSVs into a reproducible DuckDB database for exploration. Python 3.10+ is required. No database server, API key or frontend is needed.

## Run in Git Bash

From the repository directory:

```bash
git switch setup/data-access-audit
git pull --ff-only origin setup/data-access-audit
python -m pip install -r requirements.txt
python scripts/build_database.py --download
python -m unittest discover -s tests -v
```

The only new dependency is DuckDB 1.4.3, pinned to the version tested here. The download flag fetches missing files from the publisher-linked public Kaggle distribution and reuses existing files. Allow approximately 250 MB for CSVs plus database and temporary-build space. Denied downloads stop; no access bypass is attempted. Do not run simultaneous builds or keep the output database open while replacing it, especially on Windows.

Outputs (ignored by Git):

- `data/processed/football.duckdb`: local database.
- `data/processed/football.build.json`: counts, integrity checks and league-season coverage.
- `data/raw/public_audit/transfermarkt-kaggle/`: cached source CSVs.

Once cached, build entirely offline with `python scripts/build_database.py`. Custom paths are supported through `--data-dir` and `--output`. Cached files are not refreshed automatically. Use a separate data directory to audit a new snapshot. Failed validation preserves the previous database.

## Model

| Object | Grain and purpose |
|---|---|
| `matches` | One domestic league match; five leagues, season starts 2021–2025 |
| `player_match_stats` | One player/match; historical club, minutes, goals and assists |
| `players` | Player identity; position and citizenship are snapshot attributes |
| `clubs` | Club identity; name is a snapshot attribute |
| `competitions` | Competition identity and name |
| `source_files` | Input filenames, expected Kaggle URLs, SHA-256 hashes and load time |
| `player_club_season` | One player/club/competition/season; totals and per-90 statistics |
| `player_season` | One player/competition/season, aggregating transfers without duplicate totals |
| `match_coverage` | Missing or suspicious appearance coverage by match |
| `league_season_coverage` | All 25 league-season cells, expected match counts and warnings |
| `club_season_coverage` | Scheduled matches and missing club appearance records |

Season `2024` means 2024/25. IDs belong to Transfermarkt; do not join them directly to API-Football IDs. Historical membership uses `player_club_id`, never the player's current club. Cross-league transfers produce separate competition totals. Position is not a verified historical role and should not be used as a historical forecasting feature.

A missing metric makes its aggregate null rather than silently summing only known values. Zero minutes yields null per-90 values. Missing matches are not invented or filled with zeros. Coverage flags describe the club or league, not proof that an individual player missed an appearance. At least 22 rows and two clubs is only a structural check, not proof of complete match records. Club-level flags detect wholly missing club records; use match/league flags to inspect partial coverage too.

## Verified build, 28 October 2026

The published source files were downloaded and the SQL was executed against actual data:

| Result | Count |
|---|---:|
| Matches | 8,908 |
| Player-match rows | 272,457 |
| Players | 5,526 |
| Clubs | 130 |
| Competitions | 5 |
| Player-club-season rows | 14,055 |
| Player-competition-season rows | 13,676 |

All reference and integrity checks passed. All 25 cells match expected schedule counts. One match lacks appearances: `4635303`, Ligue 1 2025/26, listed as Nantes–Toulouse on 17 May 2026. See [build evidence](database_build_2026-10-28.json). Twenty offline tests pass, including transfer aggregation, null versus zero, duplicate rejection, wrong-club rejection, repeat builds and preservation of the existing database after failure.

## Query from Python

```python
import duckdb

with duckdb.connect('data/processed/football.duckdb', read_only=True) as db:
    result = db.execute('''
        SELECT player_name, minutes, goals, assists,
               ROUND(goals_per90, 3) AS goals_per90,
               league_matches_missing_appearances
        FROM player_season
        WHERE competition_id = ? AND season = ? AND minutes >= 900
        ORDER BY goals DESC, minutes ASC, player_id
        LIMIT 20
    ''', ['GB1', 2024]).fetchall()
    for row in result:
        print(row)
```

## Remaining scope

This is a local analytical prototype. Structural checks do not independently establish metric accuracy. The API-Football comparison of 20 mapped players remains pending because the user's full local import is not available here. Underlying data-use and redistribution rights remain unresolved; this step does not approve public deployment or redistribution of the raw data. See [source audit](PUBLIC_DATA_AUDIT.md).

Champions League, international competitions, advanced metrics, trophies and Ballon d'Or rankings are not included yet. No forecast is trained. Next: validate a small set of player-season totals against an independent source, then build the local Streamlit player explorer with coverage warnings.
