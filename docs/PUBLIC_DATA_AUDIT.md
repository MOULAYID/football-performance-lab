# Five-season public dataset audit

Scope: the five completed seasons 2021/22–2025/26, across the Premier League, La Liga, Serie A, Bundesliga, and Ligue 1. This evaluates published datasets, not live scraping of football websites.

## Observed results — 28 October 2026

The top-five dataset was downloaded successfully and audited using `scripts/audit_public_data.py`. The Transfermarkt published download returned HTTP 403 from the execution environment, so row-level coverage remains unverified. This does not prove the same download will fail on a local computer.

| Candidate | Result | Decision |
|---|---|---|
| m-mahadi/top5-football-dataset | 5,693 records, 220 source columns; 10 of 25 league-season combinations present | Useful candidate for the two recent seasons; not accepted as a clean merged source |
| dcaribou/transfermarkt-datasets | Published CSV download blocked (403); no match/appearance rows audited | Try the normal published download locally; stop if denied |

The top-five file contains 2024/25 and 2025/26 only. Its 2021/22, 2022/23 and 2023/24 combinations are absent. All observed cells have the expected number of distinct team labels. This does not prove the correct teams or all players are present.

| League | 2024/25 records | 2025/26 records |
|---|---:|---:|
| Premier League | 574 | 551 |
| La Liga | 601 | 611 |
| Serie A | 634 | 609 |
| Bundesliga | 492 | 507 |
| Ligue 1 | 553 | 561 |

Observed checks:
- No duplicate league/season/team/player name keys or blank identity fields.
- No missing basic minutes, appearances, FBref goals or FBref assists. Upstream imputation is not ruled out.
- No negative or unparseable values in the five checked numeric fields (minutes, appearances, goals, assists, xG).
- 316 rows have no Understat xG.
- Among 5,450 comparable rows, FBref and SofaScore goals differ on 206; the largest difference is 20.
- 198 of the 206 goal discrepancies occur on rows flagged `multi_club`.
- Assists differ on 222 comparable rows; the largest difference is 9.

The concentration around transfers suggests inconsistent club-stint/season scope. It is an inference, not an independently verified diagnosis. Do not sum or interchange source-prefixed metrics until the scopes are reconciled. A strong correlation or absence of nulls is not sufficient evidence of correct joins.

No published honours table, historical forecasting dataset, or comprehensive player identity mapping has been accepted. Current SoFIFA values and attributes must be excluded from historical forecast features. Underlying data reuse/ML/publication permissions remain unresolved; auditing is not clearance to redistribute raw data or deploy it.

## Reproduce locally (Git Bash)

```bash
git switch setup/data-access-audit
git pull --ff-only origin setup/data-access-audit
python scripts/audit_public_data.py --source all
```

Python 3.10+; standard library only. No keys or extra packages are needed. A 403/401/429 stops that source with no retries, proxies, CAPTCHA handling, or access bypass. An unavailable source causes exit code 1, while preserving the report and other successful source results.

The downloader caches completed files and removes partial files after failures. Files are capped at 512 MiB each. A cached file is reused and hashed; use a new `--data-dir` for a fresh Transfermarkt snapshot. Avoid concurrent runs on the same cache.

Output: `data/processed/public_audit/report.json`. Raw CSVs are under `data/raw/public_audit/`; both directories are ignored by Git.

Audit the successful download again without network access:

```bash
python scripts/audit_public_data.py --source top5 --offline
```

This overwrites the default report with the selected source. To retain reports for separate runs, use `--output data/processed/public_audit/another_report.json`.

If the Transfermarkt download is denied, do not change identities or use bypass services. If you obtain the same files through an authorized publisher download, place `games.csv.gz` and `appearances.csv.gz` under `data/raw/public_audit/transfermarkt/` and run:

```bash
python scripts/audit_public_data.py --source transfermarkt --offline
```

Share the generated report; no API key is involved. The script's Transfermarkt checks include expected schedule counts, dates, teams, appearance coverage, duplicate player-game keys, missing statistics, and orphan appearance rows. Matching counts alone are not a full reconciliation of actual fixtures. Competition keys come from the publisher's config; domestic league counts exclude promotion/relegation playoffs and special tiebreakers.

## Provenance

- Top-five repository: https://github.com/m-mahadi/top5-football-dataset
- Pinned commit: `8940299c2c56c2c0932d3caf292336f5e1689893`
- File: `data/master/player_seasons.csv`
- Git blob: `e7752ce810d3475808cbc2822bdcb6ead7ccf79e` (checked before analysis)
- SHA-256: `72faf86d45f32eed6d7154f4d213c1e5732ce7712f234f9ba4c23eaac3fa6543`
- Transfermarkt repository: https://github.com/dcaribou/transfermarkt-datasets
- Transfermarkt publisher reports games through 6 July 2026, appearances through 28 June 2026, with collection paused. No downloaded-row confirmation here.
- Machine-readable evidence: [public_data_audit_2026-10-28.json](public_data_audit_2026-10-28.json). This contains aggregate audit results, not raw player records.

## Next validation steps

1. Establish whether the normal Transfermarkt download works locally. Audit all 25 cells, especially 2021/22 and 2025/26; do not assume configuration equals actual coverage.
2. Reconcile multi-club rows before using merged metrics: one player, one competition, one season, one historical team stint. Keep source values separate until verified.
3. When the API-Football 2024/25 import is complete, manually verify 20 player mappings and compare minutes/goals/assists by historical club. Include transfers, low-minute players and goalkeepers. No such comparison has been run because that local dataset is not available here.
4. Collect Ballon d'Or outcomes separately from official edition pages; preserve ties and dates. Team honours require sourced winner records plus evidence of player participation.
5. Only after coverage and use permissions are settled, promote a chosen source into DuckDB and the Streamlit explorer. Until then, no claim of five-season completeness or prediction readiness.

## Tests

```bash
python -m unittest discover -s tests -v
```

15 offline tests passed at this revision, including six public-audit tests for the full coverage matrix, null-versus-zero values, duplicate keys, transfer/match joins, league-size changes, denied downloads and cache reuse.
