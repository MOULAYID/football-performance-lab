# football-performance-lab

A Python-first football analytics portfolio project: audited data, SQL analysis, player comparisons and eventually an experimental award-ranking model.

Current milestone: a reproducible local DuckDB warehouse covering the Premier League, La Liga, Serie A, Bundesliga and Ligue 1 for 2021/22–2025/26. The tested snapshot contains 8,908 matches and 272,457 player appearances; one match lacks appearance records and remains explicitly flagged.

- [Build and query the database](docs/DATABASE.md)
- [Data-source coverage and limitations](docs/PUBLIC_DATA_AUDIT.md)
- [Provider access and import instructions](docs/GETTING_STARTED.md)

Python 3.10+; install `requirements.txt`, then run `python scripts/build_database.py --download`. Downloaded data and database files stay outside Git. No API key is required for this database build's tested Kaggle route.

Player totals preserve historical club stints, null values and coverage warnings. This remains a local prototype: independent metric validation and underlying data-use rights are unresolved. Streamlit, honours, international competitions and forecasting are future milestones.
