"""Local football player explorer. Run: python -m streamlit run app.py."""
import os
from pathlib import Path

import duckdb
import streamlit as st

from comparison import (APPEARANCES_HELP, COLORS, DEFAULT_METRICS, METRICS,
                        actual_values, bar_figure, display_value, maximum_scores,
                        radar_figure, radar_issues, reference_population)

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

with st.sidebar:
    st.header('Explore')
    league = st.selectbox('League', list(LEAGUES), format_func=LEAGUES.get, key='league')
    season = st.selectbox('Season', list(range(2025, 2020, -1)), format_func=lambda y: f'{y}/{str(y+1)[-2:]}', key='season')
    min_minutes = st.number_input('Minimum minutes', min_value=0, max_value=4000, value=900, step=90, key='minutes')
    search = st.text_input('Player name', key='search')
    st.caption('Positions describe the source snapshot, not necessarily the player’s role in this season.')

cell = coverage[(coverage.competition_id == league) & (coverage.season == season)].iloc[0]
if not cell.expected_count_matches:
    st.warning(f'Match coverage differs from the expected schedule: {cell.match_count} / {cell.expected_match_count}.')
if cell.matches_with_suspect_coverage:
    st.warning(f'{cell.matches_missing_appearances} match(es) lack appearances; {cell.matches_with_suspect_coverage} match(es) have suspect coverage (including missing matches). Totals may be incomplete.')

subset = players[(players.competition_id == league) & (players.season == season)]
positions = sorted(subset.position_snapshot.dropna().unique())
position = st.sidebar.selectbox('Position snapshot', ['All'] + positions, key='position')
reference = reference_population(players, league, season, min_minutes, position)
filtered = reference
if search:
    filtered = filtered[filtered.player_name.str.contains(search, case=False, regex=False, na=False)]
filtered = filtered.sort_values(['goals', 'minutes', 'player_id'], ascending=[False, False, True], na_position='last')
cols = st.columns(3)
cols[0].metric('Players matching filters', len(filtered))
cols[1].metric('Recorded matches', int(cell.match_count))
cols[2].metric('Matches missing appearances', int(cell.matches_missing_appearances))

explore, compare, methodology = st.tabs(['Players', 'Compare players', 'Data & methodology'])
fields = ['player_name', 'position_snapshot', 'recorded_appearances', 'minutes', 'goals', 'assists', 'goals_per90', 'assists_per90', 'clubs_played_for']
with explore:
    st.subheader(f'{LEAGUES[league]} · {season}/{str(season+1)[-2:]}')
    st.caption('League totals include all clubs played for within this competition. Missing metrics remain blank. Players with unknown minutes are excluded by the minutes filter.')
    if filtered.empty:
        st.info('No players match these filters. Lower the minutes threshold or clear the name filter.')
    else:
        st.dataframe(filtered[fields].round(3), hide_index=True, width='stretch')
with compare:
    labels = {int(row.player_id): f'{row.player_name} · ID {row.player_id}' for row in filtered.itertuples()}
    # Only remove invalid selections when filters change, never on chart switches.
    if 'players' in st.session_state:
        st.session_state.players = [pid for pid in st.session_state.players if pid in labels]
    chosen = st.multiselect('Choose up to four players from the filtered list', list(labels), format_func=labels.get, max_selections=4, key='players')
    metrics = st.multiselect('Comparison metrics', list(METRICS), default=DEFAULT_METRICS,
                             format_func=METRICS.get, key='comparison_metrics')
    chart_type = st.radio('Chart type', ['Bars', 'Radar'], horizontal=True, key='chart_type')
    st.caption(APPEARANCES_HELP)
    st.caption('Appearances count matches played, not starts or unused-bench selections. '
               'They cover this domestic league only and combine historical club stints within the season.')
    st.caption('Per 90 = total ÷ minutes played × 90. Zero or unknown minutes give an unavailable rate. '
               'Rates are not adjusted for position, team strength, penalties or opposition. '
               'All totals, including appearances, may be incomplete where appearance coverage is missing.')
    if not metrics:
        st.info('Select one or more comparison metrics to display charts and values.')
    if chosen:
        selected = filtered.set_index('player_id', drop=False).loc[chosen].copy()
        # Preserve colours for retained players even when selections are edited.
        colors = {pid: color for pid, color in st.session_state.get('comparison_colors', {}).items() if pid in chosen}
        for pid in chosen:
            if pid not in colors:
                colors[pid] = next(color for color in COLORS if color not in colors.values())
        st.session_state.comparison_colors = colors
        if chart_type == 'Bars' and metrics:
            columns = st.columns(2)
            for index, metric in enumerate(metrics):
                with columns[index % 2]:
                    st.plotly_chart(bar_figure(selected, metric, colors), use_container_width=True,
                                    key=f'bar_{metric}', config={'displayModeBar': False})
        elif chart_type == 'Radar':
            scores, summary = maximum_scores(reference, metrics)
            st.caption(f'Reference: {LEAGUES[league]} · {season}/{str(season+1)[-2:]} · '
                       f'minimum {min_minutes} minutes · position: {position} · {len(reference)} players. '
                       'Name search and comparison selections do not restrict this population. '
                       'Positions are source snapshots, not verified historical roles.')
            st.dataframe(summary, hide_index=True, width='stretch')
            st.caption('Percentage of reference maximum = 100 × actual value ÷ reference maximum. '
                       'The maximum uses the full reference population, not just selected players. '
                       'At least two valid observations are required.')
            issues = radar_issues(selected, metrics, scores, summary)
            for issue in issues:
                st.warning(issue)
            constants = summary.loc[summary.Status.str.startswith('Constant'), 'Metric'].tolist()
            if constants:
                st.warning('Constant reference metrics: ' + ', '.join(constants) +
                           '. All valid values receive 100%; these axes do not distinguish players.')
            if not issues:
                st.plotly_chart(radar_figure(selected, metrics, scores, colors), use_container_width=True,
                                key='radar', theme=None, config={'displayModeBar': False})
            st.caption('These percentages preserve proportional differences, not percentile ranks or overall quality. '
                       'Extreme reference values can compress other players. Missing values are excluded per metric. '
                       'Minutes and appearances measure participation. Attacking metrics do not fairly '
                       'summarize defenders or goalkeepers. Related metrics such as goals and goals per 90, '
                       'or appearances and minutes, can make the profile repetitive. No overall score is calculated.')
        st.subheader('Actual values')
        st.dataframe(actual_values(selected, metrics), hide_index=True, width='stretch')
        st.subheader('Historical club stints')
        detail = stints[(stints.competition_id == league) & (stints.season == season) & stints.player_id.isin(chosen)]
        detail = detail[['player_name', 'club_name_snapshot', 'recorded_appearances', 'minutes', 'goals', 'assists', 'matches_missing_club_appearances']].copy()
        for metric in ['recorded_appearances', 'minutes', 'goals', 'assists']:
            detail[metric] = detail[metric].map(lambda v, m=metric: display_value(v, m))
        st.dataframe(detail.rename(columns={'player_name': 'Player', 'club_name_snapshot': 'Club (source snapshot)',
                                           **METRICS, 'matches_missing_club_appearances': 'Matches missing club appearances'}),
                     hide_index=True, width='stretch')
    else:
        st.info('Select players to compare their totals and historical club stints.')
with methodology:
    st.markdown('''Data: publisher-linked [Transfermarkt datasets on Kaggle](https://www.kaggle.com/datasets/davidcariboo/player-scores). This is a local exploratory prototype; underlying redistribution rights remain unresolved.

Totals are calculated from recorded player-match rows, using the historical club ID. A missing metric makes that aggregate unknown; zero minutes produces no per-90 value. Coverage checks flag structural gaps but cannot prove metric accuracy.

A small 2024/25 spot check agrees with official reports for Salah’s goals and assists, Kane’s goals, and Mbappé’s goals. Minutes and a representative sample of transfers, defenders and goalkeepers still need independent validation. See `docs/SAMPLE_VALIDATION.md` for evidence.

Domestic leagues only. Trophies, Ballon d’Or rankings, Champions League, international matches and predictions are not included yet.''')
    st.dataframe(coverage.sort_values(['competition_id', 'season']), hide_index=True, width='stretch')
