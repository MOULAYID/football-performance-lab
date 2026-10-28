"""Single-season and combined-period comparisons using one shared workflow."""
import pandas as pd
from comparison import (METRICS, DEFAULT_METRICS, COLORS, actual_values, display_value,
                        maximum_scores, radar_issues, radar_figure, bar_figure)
from performance import season_label


def period_totals(players, league, start, end):
    """Sum known season aggregates; never average rates or fill missing seasons."""
    scope = players[(players.competition_id == league) & players.season.between(start, end)]
    records = []
    for player_id, group in scope.groupby('player_id', sort=True):
        years = set(group.season)
        row = dict(player_id=player_id, player_name=group.iloc[0].player_name,
                   position_snapshot=group.iloc[0].position_snapshot,
                   seasons_recorded=len(years), seasons_requested=end-start+1,
                   recorded_seasons=', '.join(season_label(y) for y in sorted(years)),
                   absent_seasons=', '.join(season_label(y) for y in range(start,end+1) if y not in years) or 'None',
                   coverage_warning=bool((group.league_matches_with_suspect_coverage > 0).any() or
                                         (~group.expected_count_matches.astype(bool)).any()))
        for metric in ['goals','assists','minutes','recorded_appearances']:
            row[metric] = group[metric].sum(min_count=len(group))
        for metric in ['goals','assists']:
            row[metric+'_per90'] = (90*row[metric]/row['minutes'] if pd.notna(row['minutes']) and row['minutes']>0 else float('nan'))
        records.append(row)
    return pd.DataFrame(records, columns=['player_id','player_name','position_snapshot','seasons_recorded','seasons_requested',
                                        'recorded_seasons','absent_seasons','coverage_warning',*METRICS])


def period_reference(totals, minimum, position='All', full_seasons=False):
    mask = totals.minutes >= minimum
    if position != 'All':
        mask &= totals.position_snapshot == position
    if full_seasons:
        mask &= totals.seasons_recorded == totals.seasons_requested
    return totals.loc[mask].copy()


def render_combined(players, stints, coverage, leagues):
    import streamlit as st
    st.subheader('Compare players')
    st.caption('Compare recorded contributions in one league. Choose the same start and end season for a single-season comparison, or extend the range to combine seasons. These controls are independent of the sidebar.')
    league = st.selectbox('Comparison league', list(leagues), format_func=leagues.get, key='period_league')
    start,end = st.select_slider('Season range', options=list(range(2021,2026)), value=(2025,2025), format_func=season_label, key='period_range')
    minimum = st.number_input('Minimum minutes in selected period', min_value=0, value=900, step=90, key='period_minutes')
    totals = period_totals(players,league,start,end)
    positions = sorted(totals.position_snapshot.dropna().unique())
    position = st.selectbox('Position snapshot', ['All']+positions, key='period_position')
    full = st.checkbox('Require a player record in every selected season', key='period_full') if start != end else False
    st.caption(f'{leagues[league]} · ' + (season_label(start) if start == end else f'{season_label(start)}–{season_label(end)} · {end-start+1} seasons'))
    st.caption('Position is a source snapshot, not a historical role. The minutes threshold applies after aggregation; unknown combined minutes are excluded. '
               'A record in every season does not guarantee complete match data or a full season of participation.')
    reference = period_reference(totals,minimum,position,full)
    search = st.text_input('Find a comparison player', key='period_search')
    candidates = reference[reference.player_name.str.contains(search,case=False,regex=False,na=False)].sort_values(['player_name','player_id'])
    labels = {int(r.player_id): f'{r.player_name} · ID {r.player_id}' for r in candidates.itertuples()}
    if 'period_players' in st.session_state:
        st.session_state.period_players = [p for p in st.session_state.period_players if p in labels]
    chosen = st.multiselect('Players (up to four)', list(labels), format_func=labels.get, max_selections=4, key='period_players')
    metrics = st.multiselect('Comparison metrics', list(METRICS), default=DEFAULT_METRICS, format_func=METRICS.get, key='period_metrics')
    mode = st.radio('Chart type', ['Bars','Radar'], horizontal=True, key='period_chart')
    scope = coverage[(coverage.competition_id == league) & coverage.season.between(start,end)]
    bad = scope[(scope.matches_with_suspect_coverage>0) | (~scope.expected_count_matches.astype(bool))]
    if not bad.empty:
        st.warning('Period coverage warning: source records may be incomplete in '+', '.join(season_label(y) for y in bad.season)+'. Recorded totals and rates inherit these limitations.')
    st.caption('Appearances include substitute appearances, not unused bench selections or starts only.')
    st.caption('Goals, assists, minutes and appearances are summed over available season records, including historical same-league club stints. '
               'Per 90 = 90 × combined total ÷ combined minutes, never the average of seasonal rates. '
               'An unknown metric in any recorded season makes its combined value unavailable. '
               'Missing seasons are not filled with zero: displayed totals describe recorded contributions only, not a verified complete period or all competitions.')
    if reference.empty:
        st.info('No players match the period filters. Lower combined minutes or relax the season/position requirement.')
    if not metrics:
        st.info('Select at least one comparison metric.')
    if not chosen:
        st.info('Select players to compare their combined recorded contributions.')
        return
    selected = reference.set_index('player_id',drop=False).loc[chosen]
    colors = {p:c for p,c in st.session_state.get('period_colors',{}).items() if p in chosen}
    for p in chosen:
        if p not in colors:
            colors[p] = next(c for c in COLORS if c not in colors.values())
    st.session_state.period_colors = colors
    if (selected.seasons_recorded < selected.seasons_requested).any():
        st.warning('Incomplete season coverage: some players lack records in selected seasons. Totals are not equivalent full-period comparisons. See recorded and absent seasons below.')
    if selected.seasons_recorded.nunique()>1:
        st.warning('Unequal season counts: selected players contributed different numbers of recorded seasons. Consider the every-season filter; even then minutes may differ.')
    st.dataframe(selected[['player_name','seasons_recorded','seasons_requested','recorded_seasons','absent_seasons','coverage_warning']].rename(columns={
        'player_name':'Player','seasons_recorded':'Seasons with records','seasons_requested':'Seasons selected','recorded_seasons':'Recorded seasons',
        'absent_seasons':'Seasons without records','coverage_warning':'Source coverage warning'}),hide_index=True,width='stretch')
    if mode=='Bars':
        for i in range(0,len(metrics),2):
            for col,metric in zip(st.columns(2),metrics[i:i+2]):
                with col:
                    st.plotly_chart(bar_figure(selected,metric,colors),use_container_width=True,key=f'period_bar_{metric}',config={'displayModeBar':False})
    else:
        scores, summary = maximum_scores(reference,metrics)
        st.caption(f'Reference: {leagues[league]}, {season_label(start)}–{season_label(end)}, minimum {minimum} combined minutes, '
                   f'position {position}, every-season records required: {full}. {len(reference)} players. '
                   'Search and selected players do not restrict this population. Each axis is 100 × combined value ÷ reference maximum, not a percentile or rating.')
        st.dataframe(summary,hide_index=True,width='stretch')
        issues = radar_issues(selected,metrics,scores,summary)
        for issue in issues:
            st.warning(issue)
        constants = summary.loc[summary.Status.str.startswith('Constant'),'Metric'].tolist()
        if constants:
            st.warning('Constant reference metrics: '+', '.join(constants)+'. All receive 100%; these axes do not distinguish players.')
        if not issues:
            st.plotly_chart(radar_figure(selected,metrics,scores,colors),use_container_width=True,theme=None,key='period_radar',config={'displayModeBar':False})
        st.caption('Extreme maxima can compress other players. Minutes and appearances measure participation; related metrics repeat information. '
                   'These attacking measures do not fairly summarize defenders or goalkeepers. No overall score is calculated.')
    st.subheader('Actual values' if start == end else 'Combined recorded values')
    st.dataframe(actual_values(selected,metrics),hide_index=True,width='stretch')
    st.subheader('Season and historical club details')
    detail = stints[(stints.competition_id==league) & stints.season.between(start,end) & stints.player_id.isin(chosen)].copy()
    detail['Season'] = detail.season.map(season_label)
    for metric in METRICS:
        detail[METRICS[metric]] = detail[metric].map(lambda v,m=metric:display_value(v,m))
    st.dataframe(detail.sort_values(['player_id','season','club_id'])[['player_name','Season','club_name_snapshot',*METRICS.values(),'matches_missing_club_appearances']].rename(columns={
        'player_name':'Player','club_name_snapshot':'Club (source name)','matches_missing_club_appearances':'Matches missing club appearances'}),hide_index=True,width='stretch')
