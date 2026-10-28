"""Single-season and combined-period comparisons using one shared workflow."""
import pandas as pd
from comparison import (METRICS, DEFAULT_METRICS, COLORS, actual_values, display_value,
                        maximum_scores, radar_issues, radar_figure, bar_figure)
from performance import season_label


def period_totals(players, league, start, end):
    """Sum known season aggregates; never average rates or fill missing seasons."""
    league_ids = [league] if isinstance(league, str) else list(league)
    scope = players[players.competition_id.isin(league_ids) & players.season.between(start, end)]
    if scope.duplicated(['player_id', 'competition_id', 'season']).any():
        raise ValueError('Expected one aggregate per player, league and season')
    records = []
    for player_id, group in scope.groupby('player_id', sort=True):
        years = set(group.season)
        row = dict(player_id=player_id, player_name=group.iloc[0].player_name,
                   position_snapshot=group.iloc[0].position_snapshot,
                   league_ids=tuple(sorted(group.competition_id.unique())),
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
    return pd.DataFrame(records, columns=['player_id','player_name','position_snapshot','league_ids','seasons_recorded','seasons_requested',
                                        'recorded_seasons','absent_seasons','coverage_warning',*METRICS])


def period_reference(totals, minimum, position='All', full_seasons=False):
    mask = totals.minutes >= minimum
    if position != 'All':
        mask &= totals.position_snapshot == position
    if full_seasons:
        mask &= totals.seasons_recorded == totals.seasons_requested
    return totals.loc[mask].copy()


def excluded_records(players, player_ids, selected_leagues, start, end):
    """Known excluded portions only; cannot identify activity outside our database."""
    return players[players.player_id.isin(player_ids) & ~players.competition_id.isin(selected_leagues)
                   & players.season.between(start,end)].sort_values(['player_id','season','competition_id']).copy()


def league_breakdown(players, player_ids, selected_leagues, start, end):
    parts = []
    for league in sorted(set(selected_leagues)):
        part = period_totals(players[players.player_id.isin(player_ids)], [league], start, end)
        part['competition_id'] = league
        parts.extend(part.to_dict('records'))
    return pd.DataFrame(parts)


def render_combined(players, stints, coverage, leagues):
    import streamlit as st
    st.subheader('Compare players')
    st.caption('Compare recorded contributions across selected leagues. Choose the same start and end season for a single-season comparison, or extend the range to combine seasons. These controls are independent of the sidebar.')
    selected_leagues = st.multiselect('Comparison leagues', list(leagues), default=['GB1'], format_func=leagues.get, key='period_leagues')
    league_names = ', '.join(leagues[c] for c in selected_leagues)
    start,end = st.select_slider('Season range', options=list(range(2021,2026)), value=(2025,2025), format_func=season_label, key='period_range')
    minimum = st.number_input('Minimum minutes in selected period', min_value=0, value=900, step=90, key='period_minutes')
    totals = period_totals(players,selected_leagues,start,end)
    positions = sorted(totals.position_snapshot.dropna().unique())
    if st.session_state.get('period_position', 'All') not in ['All']+positions:
        st.session_state.period_position = 'All'
    position = st.selectbox('Position snapshot', ['All']+positions, key='period_position')
    full = st.checkbox('Require a player record in every selected season', key='period_full') if start != end else False
    st.caption(f'{league_names or "No leagues selected"} · ' + (season_label(start) if start == end else f'{season_label(start)}–{season_label(end)} · {end-start+1} seasons'))
    st.caption('Position is a source snapshot, not a historical role. The minutes threshold applies after aggregation; unknown combined minutes are excluded. '
               'Every-season eligibility requires a record in at least one included league per season; it does not guarantee complete match data or full-season participation.')
    reference = period_reference(totals,minimum,position,full)
    search = st.text_input('Find a comparison player', key='period_search')
    candidates = reference[reference.player_name.str.contains(search,case=False,regex=False,na=False)].sort_values(['player_name','player_id'])
    labels = {int(r.player_id): f'{r.player_name} · {", ".join(leagues[c] for c in r.league_ids)} · ID {r.player_id}' for r in candidates.itertuples()}
    if 'period_players' in st.session_state:
        st.session_state.period_players = [p for p in st.session_state.period_players if p in labels]
    chosen = st.multiselect('Players (up to four)', list(labels), format_func=labels.get, max_selections=4, key='period_players')
    metrics = st.multiselect('Comparison metrics', list(METRICS), default=DEFAULT_METRICS, format_func=METRICS.get, key='period_metrics')
    mode = st.radio('Chart type', ['Bars','Radar'], horizontal=True, key='period_chart')
    st.warning('Statistics are not adjusted for league strength, team strength or opposition.')
    st.caption('Per-90 rates adjust for playing time, not competition difficulty. Low-minute rates can be volatile. '
               'Changing leagues can change player totals and radar reference maxima. Totals depend on participation and available records.')
    if not selected_leagues:
        st.info('Select at least one league to compare players.')
        return
    scope = coverage[coverage.competition_id.isin(selected_leagues) & coverage.season.between(start,end)]
    bad = scope[(scope.matches_with_suspect_coverage>0) | (~scope.expected_count_matches.astype(bool))]
    if not bad.empty:
        st.warning('Period coverage warning: source records may be incomplete in '+', '.join(f'{leagues[r.competition_id]} {season_label(r.season)}' for r in bad.itertuples())+'. Recorded totals and rates inherit these limitations.')
    st.caption('Appearances include substitute appearances, not unused bench selections or starts only.')
    st.caption('Goals, assists, minutes and appearances are summed over available season records, across selected leagues; historical club stints are counted once. '
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
    selected = selected.copy()
    selected['Included leagues'] = selected.league_ids.map(lambda codes: ', '.join(leagues[c] for c in codes))
    st.dataframe(selected[['player_name','Included leagues','seasons_recorded','seasons_requested','recorded_seasons','absent_seasons','coverage_warning']].rename(columns={
        'player_name':'Player','seasons_recorded':'Seasons with records','seasons_requested':'Seasons selected','recorded_seasons':'Recorded seasons',
        'absent_seasons':'Seasons without records','coverage_warning':'Source coverage warning'}),hide_index=True,width='stretch')
    if mode=='Bars':
        for i in range(0,len(metrics),2):
            for col,metric in zip(st.columns(2),metrics[i:i+2]):
                with col:
                    st.plotly_chart(bar_figure(selected,metric,colors),use_container_width=True,key=f'period_bar_{metric}',config={'displayModeBar':False})
    else:
        scores, summary = maximum_scores(reference,metrics)
        st.caption(f'Reference: {league_names}, {season_label(start)}–{season_label(end)}, minimum {minimum} combined minutes, '
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
    values = actual_values(selected,metrics)
    values.insert(1, 'Included leagues', selected['Included leagues'])
    st.dataframe(values,hide_index=True,width='stretch')
    st.subheader('Season and historical club details')
    detail = stints[stints.competition_id.isin(selected_leagues) & stints.season.between(start,end) & stints.player_id.isin(chosen)].copy()
    detail['Season'] = detail.season.map(season_label)
    detail['League'] = detail.competition_id.map(leagues)
    for metric in METRICS:
        detail[METRICS[metric]] = detail[metric].map(lambda v,m=metric:display_value(v,m))
    st.dataframe(detail.sort_values(['player_id','season','club_id'])[['player_name','Season','League','club_name_snapshot',*METRICS.values(),'matches_missing_club_appearances']].rename(columns={
        'player_name':'Player','club_name_snapshot':'Club (source name)','matches_missing_club_appearances':'Matches missing club appearances'}),hide_index=True,width='stretch')

    st.subheader('Included league subtotals')
    st.caption('These are league-specific recorded contributions, not complete-period totals.')
    breakdown = league_breakdown(players, chosen, selected_leagues, start, end)
    breakdown['League'] = breakdown.competition_id.map(leagues)
    for metric in ['minutes','recorded_appearances','goals','assists']:
        breakdown[METRICS[metric]] = breakdown[metric].map(lambda v,m=metric: display_value(v,m))
    st.dataframe(breakdown[['player_name','League','recorded_seasons','Minutes played','Appearances','Goals','Assists','coverage_warning']].rename(columns={
        'player_name':'Player','recorded_seasons':'Recorded seasons','coverage_warning':'Source coverage warning'}),hide_index=True,width='stretch')
    excluded = excluded_records(players, chosen, selected_leagues, start, end)
    if not excluded.empty:
        st.warning('Known excluded records: some selected players have records in unselected leagues during this period. The comparison includes selected leagues only.')
        excluded['League'] = excluded.competition_id.map(leagues)
        excluded['Season'] = excluded.season.map(season_label)
        st.dataframe(excluded[['player_name','League','Season']].rename(columns={'player_name':'Player'}),hide_index=True,width='stretch')
    st.caption('Excluded-record checks cover only the five leagues in this database. No excluded record does not prove that no other activity occurred; activity outside those leagues is unknown.')
