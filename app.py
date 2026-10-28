"""Local football player explorer. Run: python -m streamlit run app.py."""
import os
from pathlib import Path

import duckdb
import streamlit as st

from performance import render_performance
from combined import render_combined

from comparison import reference_population

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
    st.caption('Sidebar filters apply only to Players. Compare players and Performance over time have their own controls.')
    league = st.selectbox('League', list(LEAGUES), format_func=LEAGUES.get, key='league')
    season = st.selectbox('Season', list(range(2025, 2020, -1)), format_func=lambda y: f'{y}/{str(y+1)[-2:]}', key='season')
    min_minutes = st.number_input('Minimum minutes', min_value=0, max_value=4000, value=900, step=90, key='minutes')
    search = st.text_input('Player name', key='search')
    st.caption('Positions describe the source snapshot, not necessarily the player’s role in this season.')

cell = coverage[(coverage.competition_id == league) & (coverage.season == season)].iloc[0]

subset = players[(players.competition_id == league) & (players.season == season)]
positions = sorted(subset.position_snapshot.dropna().unique())
position = st.sidebar.selectbox('Position snapshot', ['All'] + positions, key='position')
reference = reference_population(players, league, season, min_minutes, position)
filtered = reference
if search:
    filtered = filtered[filtered.player_name.str.contains(search, case=False, regex=False, na=False)]
filtered = filtered.sort_values(['goals', 'minutes', 'player_id'], ascending=[False, False, True], na_position='last')

explore, compare, history_tab, methodology = st.tabs(['Players', 'Compare players', 'Performance over time', 'Data & methodology'])
fields = ['player_name', 'position_snapshot', 'recorded_appearances', 'minutes', 'goals', 'assists', 'goals_per90', 'assists_per90', 'clubs_played_for']
with explore:
    if not cell.expected_count_matches:
        st.warning(f'Explorer selection ({LEAGUES[league]}, {season}/{str(season+1)[-2:]}) — Match coverage differs from the expected schedule: {cell.match_count} / {cell.expected_match_count}.')
    if cell.matches_with_suspect_coverage:
        st.warning(f'Explorer selection ({LEAGUES[league]}, {season}/{str(season+1)[-2:]}) — {cell.matches_missing_appearances} match(es) lack appearances; {cell.matches_with_suspect_coverage} match(es) have suspect coverage (including missing matches). Totals may be incomplete.')

    cols = st.columns(3)
    cols[0].metric('Players matching filters', len(filtered))
    cols[1].metric('Recorded matches', int(cell.match_count))
    cols[2].metric('Matches missing appearances', int(cell.matches_missing_appearances))
    st.subheader(f'{LEAGUES[league]} · {season}/{str(season+1)[-2:]}')
    st.caption('League totals include all clubs played for within this competition. Missing metrics remain blank. Players with unknown minutes are excluded by the minutes filter.')
    if filtered.empty:
        st.info('No players match these filters. Lower the minutes threshold or clear the name filter.')
    else:
        st.dataframe(filtered[fields].round(3), hide_index=True, width='stretch')
with compare:
    render_combined(players, stints, coverage, LEAGUES)
with history_tab:
    render_performance(players, stints, LEAGUES)
with methodology:
    st.markdown('''Data: publisher-linked [Transfermarkt datasets on Kaggle](https://www.kaggle.com/datasets/davidcariboo/player-scores). This is a local exploratory prototype; underlying redistribution rights remain unresolved.

Totals are calculated from recorded player-match rows, using the historical club ID. A missing metric makes that aggregate unknown; zero minutes produces no per-90 value. Coverage checks flag structural gaps but cannot prove metric accuracy.

A small 2024/25 spot check agrees with official reports for Salah’s goals and assists, Kane’s goals, and Mbappé’s goals. Minutes and a representative sample of transfers, defenders and goalkeepers still need independent validation. See `docs/SAMPLE_VALIDATION.md` for evidence.

Domestic leagues only. Trophies, Ballon d’Or rankings, Champions League, international matches and predictions are not included yet.''')
    st.dataframe(coverage.sort_values(['competition_id', 'season']), hide_index=True, width='stretch')
