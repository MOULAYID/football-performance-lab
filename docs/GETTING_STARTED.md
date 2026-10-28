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
