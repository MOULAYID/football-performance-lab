# Dashboard UX update — 2026-10-29

## Evidence and decisions

| Area | Observed issue / reproduction | Decision |
| --- | --- | --- |
| Compare players | Select Haaland, then type Salah in the separate search: Haaland disappears. Confirmed live and in source. | Remove the duplicate search. Use the existing searchable multiselect, retain eligible player IDs across changing labels, and explain genuine filter-driven removals. |
| Players / all tabs | Players-only sidebar remains visible on other tabs and consumes chart width. | Move filters into Players. League, season and name stay visible; participation/scoring filters are expandable with an always-visible active-filter summary. |
| Players | Raw database field names, including recorded_appearances, are visible. | Friendly column labels, integer totals, three-decimal rates and an appearances tooltip. Keep numeric table values sortable; missing remains blank. |
| Compare players | Repeated long explanations, coverage table and club/league tables push results down. | Consolidate definitions in one expander. Collapse coverage when no selected-player issue exists; retain visible warnings. Group league subtotals and club details without removing either. |
| Performance over time | Ronaldo's history shows a legend overlapping the Season axis title; default table interleaves four metrics with eight change columns. | Position legends above plots, remove redundant axis title, show actual values by default and make changes opt-in. Preserve club details in an expander. |
| Data & methodology | Published app calls itself local; evidence is a non-clickable filesystem path and coverage uses raw names. | Update scope, centralize calculation rules, link sample evidence, use readable coverage labels. Add source revision under Application version for deployment verification. |

## Tab structure

- Players: local filters → active filter summary → contextual coverage warnings → league/season and compact counts → player table.
- Compare players: league/period/eligibility → searchable player selector → metrics and chart type → short interpretation caveat and expandable definitions → contextual warnings/coverage → charts → actual values → expandable league and club breakdowns → known excluded records.
- Performance over time: player/range/metrics → short interpretation note and expandable guidance → gap/coverage notices → charts → actual values with optional adjacent-season changes → expandable historical clubs.
- Data & methodology: scope/source → metric and radar definitions → coverage table and validation evidence → application revision.

No database, ingestion, source-value, aggregation or normalization changes. Radar remains 100 × combined value / reference maximum. Unknowns, zero minutes, excluded portions, historical club stints and coverage guardrails remain intact. The static duplicate search and duplicate tab headings were removed; essential warnings and detail tables were retained.

## Validation before publication

- Python 3.12; 47 automated tests, including Streamlit AppTest, pass.
- Synthetic fixtures cover nulls, zeros, insufficient/constant radar references, metric and league empty states, multi-season requirements, weighted rates, transfers and coverage warnings.
- AppTest real-data checks exercised all 25 league-season selections.
- Cristiano Ronaldo, 2021/22 Premier League + Serie A: 18 goals, 31 appearances, 2,489 minutes, one distinct season; weighted goals/90 = 0.6508638007. Premier-League-only scope identifies the known excluded Serie A portion.
- Ronaldo's history retains two 2021/22 league records and unavailable 2023/24–2025/26 seasons. Bars/Radar switching retains selection and colours.
- Actual browser inspection before publication verified the selection-loss bug, history transfer/gap presentation, legend overlap and methodology layout.
- Local AppTest is automated rendering validation, not visual browser inspection. Post-deployment visual checks are reported separately in the delivery summary. No mobile viewport resizing API was available; mobile behaviour is not claimed as tested.

## Deferred

Cold-start dataset preparation and Streamlit inactivity sleep remain hosting limitations. No paid hosting or ingestion changes were introduced. Broader independent data accuracy and underlying data-use rights remain unresolved. The shared range slider is retained to avoid adding a second conflicting season-selection workflow.

## Run

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m streamlit run app.py
```

See DEPLOYMENT.md for cloud_app.py bootstrap and the existing deployment branch.
