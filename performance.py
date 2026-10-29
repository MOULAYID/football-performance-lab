"""One-player histories using existing league-season aggregates."""
import pandas as pd
import plotly.graph_objects as go
from comparison import METRICS, COLORS, display_value


def season_label(year):
    return f'{year}/{str(year + 1)[-2:]}'


def player_history(players, stints, player_id, start, end):
    rows = players[players.player_id == player_id].copy()
    records = []
    for year in range(start, end + 1):
        season = rows[rows.season == year]
        if season.empty:
            records.append(dict(season=year, competition_id=None, clubs='Unavailable',
                                status='No record in covered leagues', **{m: None for m in METRICS}))
        for row in season.to_dict('records'):
            clubs = stints[(stints.player_id == player_id) & (stints.season == year)
                           & (stints.competition_id == row['competition_id'])]
            row['clubs'] = ', '.join(sorted(clubs.club_name_snapshot.dropna().unique())) or 'Unavailable'
            row['status'] = ('Coverage warning: totals may be incomplete' if
                             row.get('league_matches_with_suspect_coverage', 0) or
                             not row.get('expected_count_matches', True) else 'Recorded')
            records.append(row)
    return pd.DataFrame(records).sort_values(['season', 'competition_id'], na_position='last').reset_index(drop=True)


def history_table(history, metrics, leagues):
    records = []
    for row in history.to_dict('records'):
        record = {'Season': season_label(row['season']), 'League': leagues.get(row['competition_id'], 'Unavailable'),
                  'Clubs (source names)': row['clubs'], 'Coverage': row['status']}
        previous = history[history.season == row['season'] - 1]
        current = history[history.season == row['season']]
        # Do not suggest comparable full-season changes across split or different leagues.
        comparable = (len(previous) == len(current) == 1 and
                      previous.iloc[0].competition_id == row['competition_id'] and
                      row['competition_id'] is not None)
        for metric in metrics:
            value = row[metric]
            record[METRICS[metric]] = display_value(value, metric)
            prev = previous.iloc[0][metric] if comparable else None
            valid = pd.notna(value) and pd.notna(prev)
            delta = value - prev if valid else None
            record[METRICS[metric] + ' change'] = (f'{delta:+.3f}' if metric.endswith('per90') else f'{delta:+,.0f}') if valid else 'Unavailable'
            record[METRICS[metric] + ' change %'] = f'{100 * delta / prev:+.1f}%' if valid and prev != 0 else 'Unavailable'
        records.append(record)
    return pd.DataFrame(records)


def trend_figure(history, metric, leagues):
    years = sorted(history.season.unique())
    figure = go.Figure()
    for index, league in enumerate(sorted(history.competition_id.dropna().unique())):
        rows = history[history.competition_id == league].set_index('season')
        values, details = [], []
        for year in years:
            row = rows.loc[year] if year in rows.index else None
            value = row[metric] if row is not None else None
            values.append(float(value) if pd.notna(value) else None)
            details.append([display_value(value, metric), row['clubs'] if row is not None else 'Unavailable',
                            row['status'] if row is not None else 'No record in this league'])
        figure.add_trace(go.Scatter(x=[season_label(y) for y in years], y=values, mode='lines+markers',
                                   connectgaps=False, name=leagues.get(league, league),
                                   line=dict(color=(COLORS + ['#9467BD'])[index % 5]), customdata=details,
                                   hovertemplate='%{x}<br>Actual: %{customdata[0]}<br>Clubs: %{customdata[1]}<br>%{customdata[2]}<extra>%{fullData.name}</extra>'))
    figure.update_layout(title=METRICS[metric], height=340, margin=dict(l=25, r=25, t=85, b=45),
                         xaxis=dict(title=None, type='category', categoryorder='array', categoryarray=[season_label(y) for y in years]),
                         yaxis=dict(title=METRICS[metric], rangemode='tozero'), legend=dict(orientation='h', x=0, y=1.15, yanchor='bottom'))
    if not metric.endswith('per90'):
        figure.update_yaxes(tickformat=',d')
    return figure


def render_performance(players, stints, leagues):
    import streamlit as st
    st.caption('Choose a player from all five leagues. Filters here affect only this history.')
    people = players[['player_id', 'player_name']].drop_duplicates('player_id').sort_values(['player_name', 'player_id'])
    labels = {int(r.player_id): f'{r.player_name} · ID {r.player_id}' for r in people.itertuples()}
    player = st.selectbox('Player history', list(labels), index=None, format_func=labels.get, key='history_player', placeholder='Search for a player')
    start, end = st.select_slider('Season range', options=list(range(2021, 2026)), value=(2021, 2025), format_func=season_label, key='history_range')
    metrics = st.multiselect('History metrics', list(METRICS), default=['goals', 'assists', 'minutes', 'goals_per90'], format_func=METRICS.get, key='history_metrics')
    st.caption('Seasonal statistics describe recorded performance, not a player rating or proof of improvement.')
    with st.expander('How to read trends and season changes'):
        st.caption('Actual values, not normalized scores. Per 90 = total ÷ minutes × 90; unknown or zero minutes give an unavailable rate. '
                   'Higher values do not necessarily mean improvement: playing time, league, team and role can change. '
                   'Low-minute per-90 rates can be volatile; consult minutes and appearances. '
                   'Attacking statistics give a limited picture of defenders and goalkeepers.')
    if player is None:
        st.info('Select one player to view their seasonal history.')
        return
    history = player_history(players, stints, player, start, end)
    st.caption('Different leagues are separate lines, including two league records within one season. Same-league transfers are combined in seasonal totals. '
               'Missing seasons remain gaps; no record does not prove zero appearances or identify why data is absent.')
    if history.competition_id.isna().any():
        st.info('Some selected seasons have no player record in our five-league dataset. Those seasons are unavailable, not zero.')
    if history.status.str.startswith('Coverage warning').any():
        st.warning('Historical coverage warning: some league-season records may be incomplete. Check the Coverage column and club details.')
    if not metrics:
        st.info('Select at least one history metric to show trends.')
    for index in range(0, len(metrics), 2):
        for column, metric in zip(st.columns(2), metrics[index:index+2]):
            with column:
                if history[metric].notna().any():
                    st.plotly_chart(trend_figure(history, metric, leagues), use_container_width=True, key=f'history_{metric}', config={'displayModeBar': False})
                else:
                    st.info(f'{METRICS[metric]}: unavailable throughout this range.')
    st.subheader('Seasonal values and changes')
    st.caption('Changes compare adjacent selected seasons in the same league only, with one league record in each. '
               'No change is calculated across missing seasons, split-league seasons or league switches. Percentage change is unavailable when the previous value is zero. '
               'Changes inherit any coverage limitations; the first selected season has no comparison.')
    show_changes = st.checkbox('Show year-over-year changes', key='history_show_changes')
    table = history_table(history, metrics, leagues)
    if not show_changes:
        table = table[[c for c in table if not c.endswith((' change', ' change %'))]]
    st.dataframe(table, hide_index=True, width='stretch')
    detail = stints[(stints.player_id == player) & stints.season.between(start, end)].copy()
    with st.expander('Historical clubs by season'):
        if detail.empty:
            st.info('No club records in this season range.')
        else:
            detail['Season'] = detail.season.map(season_label)
            detail['League'] = detail.competition_id.map(leagues)
            for metric in METRICS:
                detail[METRICS[metric]] = detail[metric].map(lambda value, m=metric: display_value(value, m))
            st.dataframe(detail.sort_values(['season', 'competition_id', 'club_id'])[['Season', 'League', 'club_name_snapshot', *METRICS.values(), 'matches_missing_club_appearances']].rename(columns={'club_name_snapshot': 'Club (source name)', 'matches_missing_club_appearances': 'Matches missing club appearances'}), hide_index=True, width='stretch')
