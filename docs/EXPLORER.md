# Run the local player explorer

From the project folder in Git Bash:

```bash
git switch setup/data-access-audit
git pull --ff-only origin setup/data-access-audit
python -m pip install -r requirements.txt
python scripts/build_database.py --download
python -m streamlit run app.py
```

Open the local URL shown by Streamlit (normally http://localhost:8501). Stop with Ctrl+C. No JavaScript, backend server framework or API key is required. This command starts a local app; it does not publish a website.

Use league, season, name, minimum-minutes and snapshot-position filters. In Compare players, use its independent league and season-range controls to select up to four players and multiple metrics, then switch between Bars and Radar. Comparisons stay within one league and season. Missing values remain unknown, and league coverage warnings appear within the relevant view.

The app reads `data/processed/football.duckdb`. To use another database, set `FOOTBALL_DB_PATH`. Rebuilds invalidate the app cache using the file modification time; finish the build before refreshing the app.

[Database model](DATABASE.md) · [Independent sample checks](SAMPLE_VALIDATION.md)

Test with `python -m unittest discover -s tests -v`. Streamlit's AppTest exercises the app without a browser. The fixture tests cover filtering, player selection, missing database guidance and coverage warnings; they do not replace visual browser inspection.

## Comparison metrics and charts

Choose Goals, Assists, Appearances, Minutes played, Goals per 90 and Assists per 90. All except Minutes played are selected by default. Bars is the default view, with separate horizontal charts, zero-based scales and exact value labels. Players retain their colour and order across metrics and chart switches. Missing values appear as **Unavailable**, distinct from a genuine zero.

**Appearances** maps directly to `recorded_appearances`: the count of unique player-match records in the selected domestic league and season. This includes substitute appearances, not unused bench selections or starts only. The existing SQL aggregates match facts across historical club stints; it does not add current-club memberships. Individual club counts remain in Historical club stints. Missing match records can make all totals incomplete. No ingestion, schema or aggregation changes are required.

Per-90 values come directly from the database: `90 * total / minutes`. Missing aggregate values and zero or unknown minutes remain unavailable. They are displayed to three decimal places, while totals are integers.

### Radar reference and methodology

Radar requires at least three selected metrics. Its reference includes all players in the selected league and season range satisfying the comparison view’s minimum-period-minutes, snapshot-position and optional every-season filters. A single-season range reproduces single-season statistics. Players with unknown minutes are excluded, matching the existing filter. Name search restricts selection candidates only; neither search nor selected players changes the reference distribution. Positions are source snapshots, not verified historical roles.

Each metric excludes its own missing observations and uses the maximum from the full reference population:

`scaled(x) = 100 * x / reference_maximum`

This preserves ratios: with a reference maximum of 30 goals, 27 and 15 goals appear at 90% and 50%. Selecting different comparison players or changing name search does not change the denominator. Changing league, season, minutes or position filters can change it. This is a percentage of the maximum, not a percentile rank or z-score. Extreme maxima can compress other values.

Positive constant metrics receive 100% with a warning that they do not distinguish players. All-zero metrics have no valid denominator and block the radar; users must remove the metric or switch to Bars. Zeros on metrics with a positive maximum remain genuine zero scores. Fewer than two valid observations blocks the radar. The population size, valid observation counts and reference maxima are displayed; maxima are formatted for display but full precision is used for calculation.

The radar uses an explicit dark panel with contrasting labels and grid lines in either app theme, percentage ticks, and a centred legend beneath the plot. Streamlit theme overrides are disabled for this chart so the polar background and text remain consistent.

Any missing selected value also blocks the radar without dropping players or metrics. Users can remove the affected selection or switch to Bars. Actual values and historical club stints remain accessible beneath either view, including blocked radar states.

Percentages describe the share of the reference maximum, not overall quality. Minutes and appearances describe participation. These attacking metrics cannot fairly summarize defenders or goalkeepers; related axes can repeat information. No composite score is calculated.

### Dependencies and update

Plotly 6.3.1 supplies both comparison charts through Python, including native polar traces, transparent fills and raw-value/scaled-percentage hover text. Using one chart library keeps colours and interactions consistent. The existing Altair pin is retained for Streamlit compatibility. No custom JavaScript or additional server is introduced.

For an existing database, activate the Python 3.12 environment and run:

```bash
git pull --ff-only origin setup/data-access-audit
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

No database rebuild is needed for this feature.

Validation for this update: 29 offline tests pass, including chart specifications and Streamlit AppTest interaction checks. Both chart types were exercised for all 25 league-season combinations against the local database (50 views, up to four players). `pip check` reports no broken requirements under Python 3.12.14. Browser visual inspection could not be completed: no browser executable was installed and the browser download failed. Chart serialization and AppTest are automated checks, not visual inspection; Windows rendering remains to be checked locally.

## Python compatibility and isolated setup

Use Python 3.12 for this pinned stack. The earlier Python 3.10+ description was too broad: Altair 5.5 can fail on Python 3.14 with `_TypedDictMeta.__new__() got an unexpected keyword argument 'closed'` (https://github.com/vega/altair/issues/3874). Updating typing-extensions alone does not repair Altair choosing the standard-library TypedDict on that runtime.

Stop Streamlit. In Git Bash, check `python --version` and `py -0p`. If necessary, install Python 3.12 from python.org. Create a separate environment without deleting the existing one:

```bash
deactivate
py -3.12 -m venv .venv312
source .venv312/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
python -c "import altair; print(altair.__version__)"
python -m streamlit run app.py
```

Skip `deactivate` if no environment is active. This preserves downloaded data and the database. In future terminals use `source .venv312/Scripts/activate`. Verified locally: Python 3.12.14, Altair 5.5.0 and typing-extensions 4.16.0 import and serialize a bar chart successfully. Windows execution remains to be confirmed on the user's machine.

## Performance over time

The dedicated tab selects one player across the entire database, a contiguous season range (default 2021/22–2025/26), and any of the six existing metrics. Sidebar league, season, search, position and minutes filters do not restrict history. Player selection starts empty, avoiding unsolicited charts in other tabs.

Separate line charts show actual values, not radar scores. Each league is its own series with the same season axis; missing observations are gaps (`connectgaps=False`). A player in two leagues in one season has two records and two points, never an implicitly combined total. Same-league club stints remain combined by the existing database aggregate. Hover text shows clubs and coverage status; the table below includes all selected seasons, including absent records. Club names are source snapshots; memberships are historical match records.

The seasonal table gives absolute and percentage changes only when adjacent selected seasons each have one record in the same league and both metric values are known. Percentage changes are unavailable for zero baselines; absolute changes from zero remain valid. League switches, split-league seasons and missing years have no calculated change. The first selected season is not compared outside the chosen range. Coverage warnings remain visible; changes can inherit incomplete totals. A missing record does not establish zero activity or a particular reason for absence.

Goals, assists, appearances and minutes reuse stored totals. Per-90 values reuse the existing SQL calculation; zero/unknown minutes remain unavailable. No new dependencies, database changes or downloads are required. This is descriptive performance history, not a rating or proof of improvement. Role, competition and participation changes affect interpretation.

Validation: 33 tests pass in the full suite. Streamlit AppTest also loaded five real player histories, including split-league seasons and five-season records. Focused tests cover gaps, true zeros, unknown rates, within-season league changes, club labels, percentage-change rules and independent Streamlit controls. Browser visual inspection remains pending.

## Unified Compare players view

The Compare players tab has independent controls for one league, a shared contiguous season range, minimum **combined** minutes, snapshot position, and up to four players. The default range is the latest single season (2025/26). Set both handles to the same season for single-season statistics, or extend the range for combined totals. All six existing metrics are available in Bars or Radar. Name search affects candidates only; changing chart type preserves selections and colours.

Aggregation sums recorded league-season appearances, goals, assists and minutes. Existing same-league transfer aggregation is reused, so historical club stints do not duplicate totals. A null metric in any recorded season makes that combined metric null. Per-90 rates are recalculated as `90 * combined total / combined minutes`, never averaged across seasonal rates; zero or unknown minutes produce unavailable rates. Unknown combined minutes are excluded by the threshold, even at zero.

Absent seasons are not filled with zero. Totals represent **recorded contributions**, not a verified complete period or all competitions. Each player has a visible count/list of recorded seasons and a list of seasons without records. The app does not infer whether absence means a different league, no appearances, or missing source data. Incomplete and unequal season counts have warnings. For multi-season ranges, the optional every-season filter requires records in every selected season, not complete match coverage or equal playing time. Source coverage warnings and seasonal club details remain visible.

Radar uses each filtered player's combined metrics, with maxima over the full filtered aggregate population. Search and selected players never redefine that population. Scores are percentages of reference maxima, not percentiles or player ratings. Existing minimum-axis, missing-value, constant-metric, zero-maximum and insufficient-reference guardrails apply. Changing the period, league, minimum minutes, position or every-season filter can change reference maxima.

No database rebuild, dependency update or ingestion changes are needed. Test with `python -m unittest discover -s tests -v`. Focused tests cover strict null propagation, weighted per-90 rates, season coverage, zero minutes, independent controls and chart switching. Browser visual inspection remains pending.

Before consolidation, combined-period validation passed 38 tests in the full suite. Automated Streamlit checks exercised 20 real-data views (five leagues × two ranges × Bars/Radar). Five-season goals, assists, minutes and appearance totals agree with an independent SQL aggregation of the underlying match records for all 1,232 Premier League players. This validates aggregation, not independent source accuracy. No browser visual inspection was performed.


The comparison tabs are now consolidated: navigation is Players, Compare players, Performance over time, and Data & methodology. Sidebar controls and browsing counts/warnings belong only to Players. Comparison controls remain inside Compare players; history controls remain separate. Valid player/metric selections, chart type and colours survive changes between one and several seasons. Invalid player selections are removed when filters make them ineligible. The every-season checkbox appears only for multi-season ranges. Comparisons always share one league and period; different player-specific periods are not supported.

Consolidation validation: 37 tests pass after consolidating duplicate comparison UI tests. Automated real-data checks passed for 20 views (five leagues × single-season/five-season ranges × Bars/Radar). Visual browser inspection remains pending. No dependencies or database rebuild are required.

## Sidebar goals and assists filters

Players can be filtered by minimum goals and minimum assists within the sidebar-selected league and season. Both conditions apply together, alongside existing filters. Both inputs start blank (disabled); clearing an input disables it again. Setting a threshold, including zero, excludes unknown values for that metric without converting missing data into zero. The matching-player count updates accordingly. These browsing filters do not affect Compare players, radar reference populations or Performance over time.
