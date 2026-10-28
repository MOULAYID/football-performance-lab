"""Local football player explorer. Run: python -m streamlit run app.py."""
import os
from pathlib import Path

import duckdb
import streamlit as st

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
filtered = subset[subset.minutes >= min_minutes]
if search:
    filtered = filtered[filtered.player_name.str.contains(search, case=False, regex=False, na=False)]
if position != 'All':
    filtered = filtered[filtered.position_snapshot == position]
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
    chosen = st.multiselect('Choose up to four players from the filtered list', list(labels), format_func=labels.get, max_selections=4, key='players')
    if chosen:
        selected = filtered[filtered.player_id.isin(chosen)].copy()
        st.dataframe(selected[fields].round(3), hide_index=True, width='stretch')
        metric = st.selectbox('Chart metric', ['goals', 'assists', 'minutes', 'goals_per90', 'assists_per90'], key='metric')
        selected['label'] = selected.player_name + ' · ' + selected.player_id.astype(str)
        chart = selected[['label', metric]].dropna(subset=[metric])
        if len(chart) < len(selected):
            st.info('Players with missing values for this metric are omitted from the chart.')
        if not chart.empty:
            st.bar_chart(chart.set_index('label'), horizontal=True)
        st.caption('Per-90 values are not adjusted for position, team strength, penalties or opposition.')
        st.subheader('Historical club stints')
        detail = stints[(stints.competition_id == league) & (stints.season == season) & stints.player_id.isin(chosen)]
        st.dataframe(detail[['player_name', 'club_name_snapshot', 'recorded_appearances', 'minutes', 'goals', 'assists', 'matches_missing_club_appearances']], hide_index=True, width='stretch')
    else:
        st.info('Select players to compare their totals and historical club stints.')
with methodology:
    st.markdown('''Data: publisher-linked [Transfermarkt datasets on Kaggle](https://www.kaggle.com/datasets/davidcariboo/player-scores). This is a local exploratory prototype; underlying redistribution rights remain unresolved.

Totals are calculated from recorded player-match rows, using the historical club ID. A missing metric makes that aggregate unknown; zero minutes produces no per-90 value. Coverage checks flag structural gaps but cannot prove metric accuracy.

A small 2024/25 spot check agrees with official reports for Salah’s goals and assists, Kane’s goals, and Mbappé’s goals. Minutes and a representative sample of transfers, defenders and goalkeepers still need independent validation. See `docs/SAMPLE_VALIDATION.md` for evidence.

Domestic leagues only. Trophies, Ballon d’Or rankings, Champions League, international matches and predictions are not included yet.''')
    st.dataframe(coverage.sort_values(['competition_id', 'season']), hide_index=True, width='stretch')
