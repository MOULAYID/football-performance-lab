# First milestone: verify data access

This is a Python-first football analytics project. Start with one league and one accessible completed season. Add DuckDB and Streamlit after verifying actual coverage; award forecasting comes later.

## Setup (Windows PowerShell)

```powershell
git clone https://github.com/MOULAYID/football-performance-lab.git
cd football-performance-lab
py -m venv .venv
.\.venv\Scripts\python.exe scripts/check_access.py --provider football-data
.\.venv\Scripts\python.exe scripts/check_access.py --provider api-football --league 39
```

Python 3.10 or later is required. The checker uses only the standard library: no pip installation is needed yet. Run on a local terminal. Each command prompts for a credential with hidden input. API-Football expects your direct dashboard key, not a RapidAPI key. Credentials are not saved. Alternatively, use the FOOTBALL_DATA_TOKEN and API_FOOTBALL_KEY environment variables; the script does not load .env files.

For macOS/Linux use `python3 -m venv .venv` and `.venv/bin/python` in place of the Windows commands.

## Sample an accessible season

After reviewing the listed seasons and your plan, choose a season start year. This example uses 2023; it is not a promise that your plan includes it:

```powershell
.\.venv\Scripts\python.exe scripts/check_access.py --provider api-football --league 39 --season 2023
```

Without --season, each invocation makes one request. With --season, API-Football makes two requests (league metadata plus the first player page). There are no automatic retries or full downloads. The report lists missing fields, IDs, and pagination without printing player records or account details.

A listed season or a true coverage flag does not establish subscription access or completeness. An empty response is not a successful coverage test. A first-page sample does not represent the full league. The later importer must fetch all pages, respect quotas, reconcile transferred players and validate unique player/team/competition/season records.

Record the chosen league, season, sample size, missing fields, total pages, and access failures. Missing assists must not automatically become zero. Share only the report, never the credentials. The football-data competition list provides context, not player-statistic coverage.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests are offline and do not consume API requests. Live access still needs validation using your own credentials.

## Next deliverable

Once a usable season is confirmed: implement paginated ingestion, validate player identities and team stints, store curated statistics in DuckDB, and add a Streamlit player comparison page. Review provider publication and redistribution terms before including provider datasets in the public repository or demo.

References:
- https://www.api-football.com/documentation_v3
- https://docs.football-data.org/general/v4/lookup_tables.html
- https://www.api-football.com/terms
- https://www.football-data.org/about

## Verified access and full local import

The user's access audit confirmed Premier League 2024/25 player access (league 39, season 2024). The free plan rejected season 2025 and reported an allowed range of 2022–2024. The first page had 20 player records, 21 matching statistic rows and 57 total pages. These are observed sample results, not a completeness guarantee.

From Git Bash, after updating this branch:

```bash
python scripts/import_players.py --league 39 --season 2024
```

No packages are required. The importer prompts for the direct API-Football key, spaces new requests seven seconds apart, and defaults to at most 35 new requests per invocation. Check your dashboard's remaining quota first and lower the cap with `--max-requests 10` if needed. The cap does not measure your remaining daily allowance. Other tools and earlier audits also consume quota.

Repeat the same command to resume. Completed pages are read from the local cache without new requests. With 57 pages and a 35-request cap, two runs are needed (35 then 22 requests), provided your quota allows it. The previous access check did not cache its sample, so page 1 is fetched again.

Outputs (ignored by Git):
- `data/raw/api-football_39_2024_initial/`: dated page snapshots.
- `data/processed/api-football_39_2024_initial/players.csv`: validated player/team/league/season records.
- `data/processed/api-football_39_2024_initial/quality_report.json`: counts and missing-field summary.

CSV empty cells represent nulls; zeros are retained. Multiple teams for the same player remain separate. Identical repeated statistic rows are deduplicated and counted; conflicting rows or repeated players across pages stop the export. Every player must have at least one matching league-season statistic row.

If the provider changes pagination during a download, the importer stops. Use a new name, e.g. `--snapshot refresh1`, to start a separate download without deleting the old cache. Do not run multiple importers against the same snapshot concurrently. A complete pagination download is not proof of complete real-world coverage; updates during download can still cause omissions that require independent reconciliation.

The importer has offline fixture tests, but a full live download has not yet been verified. Share the final quality report rather than raw player data. Next: inspect null semantics, reconcile team coverage, then build DuckDB tables and the Streamlit explorer.
