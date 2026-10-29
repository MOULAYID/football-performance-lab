"""Local football player explorer. Run: python -m streamlit run app.py."""
import os
import subprocess
from pathlib import Path

import duckdb
import streamlit as st

from performance import render_performance
from combined import render_combined

from comparison import reference_population, METRICS, APPEARANCES_HELP

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('FOOTBALL_DB_PATH', ROOT / 'data/processed/football.duckdb'))
LEAGUES = {'GB1': 'Premier League', 'ES1': 'La Liga', 'IT1': 'Serie A', 'L1': 'Bundesliga', 'FR1': 'Ligue 1'}

st.set_page_config(page_title='Football Performance Lab', page_icon='⚽', layout='wide')
st.title('Football Performance Lab')
st.caption('Explore five seasons of domestic league football · 2021/22–2025/26')
if not DB.is_file():
    st.info('Build the local database first, then refresh this page.')
    st.code('python scripts/build_database.py --download', language='bash')
    st.stop()

@st.cache_data(show_spinner=False)
def load_data(path, modified_ns):
    # A fresh read-only connection avoids sharing mutable connections across sessions.
    with duckdb.connect(path, read_only=True) as db:
        return (
            db.execute('SELECT * FROM player_season').fetchdf(),
            db.execute('SELECT * FROM player_club_season').fetchdf(),
            db.execute('SELECT * FROM league_season_coverage').fetchdf(),
        )

try:
    players, stints, coverage = load_data(str(DB), DB.stat().st_mtime_ns)
except (duckdb.Error, OSError) as exc:
    st.error('The database could not be opened. Close any active build and rebuild if its schema is outdated.')
    st.stop()

explore, compare, history_tab, methodology = st.tabs(['Players', 'Compare players', 'Performance over time', 'Data & methodology'])
fields = ['player_name', 'position_snapshot', 'recorded_appearances', 'minutes', 'goals', 'assists', 'goals_per90', 'assists_per90', 'clubs_played_for']
with explore:
    st.caption('Browse one domestic league and season. Filters on this tab affect only this table.')
    first = st.columns(3)
    league = first[0].selectbox('League', list(LEAGUES), format_func=LEAGUES.get, key='league')
    season = first[1].selectbox('Season', list(range(2025, 2020, -1)), format_func=lambda y: f'{y}/{str(y+1)[-2:]}', key='season')
    search = first[2].text_input('Player name', key='search', placeholder='Search this league and season')
    subset = players[(players.competition_id == league) & (players.season == season)]
    positions = sorted(subset.position_snapshot.dropna().unique())
    if st.session_state.get('position', 'All') not in ['All'] + positions:
        st.session_state.position = 'All'
    with st.expander('Participation, position and scoring filters'):
        filters = st.columns(4)
        min_minutes = filters[0].number_input('Minimum minutes', min_value=0, max_value=4000, value=900, step=90, key='minutes')
        position = filters[1].selectbox('Position snapshot', ['All'] + positions, key='position',
                                      help='Source snapshot, not a verified historical role.')
        min_goals = filters[2].number_input('Minimum goals', min_value=0, value=None, step=1,
                                          placeholder='No minimum', key='min_goals')
        min_assists = filters[3].number_input('Minimum assists', min_value=0, value=None, step=1,
                                            placeholder='No minimum', key='min_assists')
        st.caption('Goals and assists minimums apply together. Clear a minimum to disable it. Unknown values cannot satisfy an active minimum.')
    cell = coverage[(coverage.competition_id == league) & (coverage.season == season)].iloc[0]
    reference = reference_population(players, league, season, min_minutes, position)
    filtered = reference
    if min_goals is not None:
        filtered = filtered[filtered.goals >= min_goals]
    if min_assists is not None:
        filtered = filtered[filtered.assists >= min_assists]
    if search:
        filtered = filtered[filtered.player_name.str.contains(search, case=False, regex=False, na=False)]
    filtered = filtered.sort_values(['goals', 'minutes', 'player_id'], ascending=[False, False, True], na_position='last')
    active = f'Minutes ≥ {min_minutes} · Position: {position}'
    if min_goals is not None:
        active += f' · Goals ≥ {min_goals}'
    if min_assists is not None:
        active += f' · Assists ≥ {min_assists}'
    st.caption(active)
    if not cell.expected_count_matches:
        st.warning(f'Explorer selection ({LEAGUES[league]}, {season}/{str(season+1)[-2:]}) — Match coverage differs from the expected schedule: {cell.match_count} / {cell.expected_match_count}.')
    if cell.matches_with_suspect_coverage:
        st.warning(f'Explorer selection ({LEAGUES[league]}, {season}/{str(season+1)[-2:]}) — {cell.matches_missing_appearances} match(es) lack appearances; {cell.matches_with_suspect_coverage} match(es) have suspect coverage (including missing matches). Totals may be incomplete.')

    st.subheader(f'{LEAGUES[league]} · {season}/{str(season+1)[-2:]}')
    st.caption(f'{len(filtered):,} players matching filters · {int(cell.match_count):,} recorded matches · '
               f'{int(cell.matches_missing_appearances)} matches missing appearances')
    st.caption('Totals include historical club stints in this league. Blank values are unavailable, not zero. Unknown minutes are excluded by the minutes filter.')
    if filtered.empty:
        st.info('No players match these filters. Lower or clear the goals/assists minimums, lower the minutes threshold, or adjust the name and position filters.')
    else:
        st.dataframe(filtered[fields], hide_index=True, width='stretch', column_config={
            'player_name': 'Player', 'position_snapshot': 'Position (snapshot)',
            'clubs_played_for': st.column_config.NumberColumn('Clubs played for', format='%d', help='Number of distinct historical clubs in this league and season.'),
            **{m: st.column_config.NumberColumn(label, format='%.3f' if m.endswith('per90') else '%d',
                                               help=APPEARANCES_HELP if m == 'recorded_appearances' else None)
               for m, label in METRICS.items()},
        })
with compare:
    render_combined(players, stints, coverage, LEAGUES)
with history_tab:
    render_performance(players, stints, LEAGUES)
with methodology:
    st.subheader('Scope and source')
    st.markdown('Five domestic leagues, 2021/22–2025/26. Data comes from the publisher-linked '
                '[Transfermarkt datasets on Kaggle](https://www.kaggle.com/datasets/davidcariboo/player-scores). '
                'Underlying data-use and redistribution rights remain unresolved. '
                'Trophies, international and cup competitions, player ratings and predictions are outside this dataset.')
    st.subheader('How to read the statistics')
    st.markdown('- **Totals:** recorded player-match rows, attributed to historical club IDs. Club names and positions are source snapshots.\n- **Appearances:** recorded matches played, including substitutes; not starts only or unused-bench selections. Missing source records can make totals incomplete.\n- **Per 90:** 90 × metric total ÷ minutes. Combined periods use combined totals and minutes, never an average of rates. Zero or unknown minutes produce no rate.\n- **Missing data:** an unknown metric makes its aggregate unavailable. Missing seasons are not filled with zero. A record in every season does not guarantee full-season participation or complete match coverage.\n- **Radar:** 100 × player value ÷ eligible reference maximum. Reference filters include leagues, period, aggregate minutes, position and every-season eligibility; search and selected players do not restrict it. Missing observations are excluded per metric. Fewer than two valid observations or a zero maximum blocks that axis; positive constants receive 100 with a warning.\n- **Interpretation:** statistics are not adjusted for league, team or opposition strength. Participation affects totals; low-minute rates can be volatile. Radar percentages are not ratings, and attacking metrics do not fairly summarize defenders or goalkeepers. Related metrics can repeat information.')
    st.subheader('Coverage and validation')
    st.caption('Structural checks identify missing or suspect appearance records; they do not prove metric accuracy.')
    report = coverage.sort_values(['competition_id', 'season']).copy()
    report['League'] = report.competition_id.map(LEAGUES)
    report['Season'] = report.season.map(lambda y: f'{y}/{str(y+1)[-2:]}')
    report = report.drop(columns=['competition_id', 'season']).rename(columns={
        'match_count': 'Recorded matches', 'expected_match_count': 'Expected matches',
        'matches_missing_appearances': 'Matches missing appearances',
        'matches_with_suspect_coverage': 'Matches with suspect coverage',
        'expected_count_matches': 'Schedule count matches', 'first_match': 'First match', 'last_match': 'Last match'})
    st.dataframe(report[['League', 'Season'] + [c for c in report if c not in ['League', 'Season']]], hide_index=True, width='stretch')
    st.markdown('A small 2024/25 spot check agrees with official reports for Salah’s goals and assists, Kane’s goals and Mbappé’s goals. '
                'Minutes and a representative sample of transfers, defenders and goalkeepers still need independent validation. '
                '[Read the sample evidence](https://github.com/MOULAYID/football-performance-lab/blob/setup/data-access-audit/docs/SAMPLE_VALIDATION.md).')
    with st.expander('Application version'):
        try:
            revision = subprocess.check_output(
                ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL,
                text=True, timeout=2).strip()
        except (OSError, subprocess.SubprocessError):
            revision = None
        if revision:
            st.caption(f'Source revision: {revision}')
        else:
            st.caption('Source revision is unavailable in this hosting environment.')
