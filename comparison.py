"""Comparison filtering, midrank percentiles and Python-only Plotly figures."""
import pandas as pd
import plotly.graph_objects as go

METRICS = {
    'goals': 'Goals', 'assists': 'Assists',
    'recorded_appearances': 'Appearances', 'minutes': 'Minutes played',
    'goals_per90': 'Goals per 90', 'assists_per90': 'Assists per 90',
}
DEFAULT_METRICS = ['goals', 'assists', 'recorded_appearances', 'goals_per90', 'assists_per90']
COLORS = ['#0072B2', '#D55E00', '#009E73', '#CC79A7']
APPEARANCES_HELP = ('Recorded match appearances, including substitute appearances, in the selected '
                    'league and season. Missing source records may make this total incomplete.')


def reference_population(players, league, season, min_minutes, position='All'):
    mask = ((players.competition_id == league) & (players.season == season)
            & (players.minutes >= min_minutes))
    if position != 'All':
        mask &= players.position_snapshot == position
    return players.loc[mask].copy()


def percentile_scores(reference, metrics):
    """Midrank: 100 * (count below + 0.5 * count equal) / valid count.

    Missing values are excluded per metric. Fewer than two observations yield
    unavailable scores; constant populations of size >=2 yield 50 for everyone.
    """
    scores = pd.DataFrame(index=reference.player_id)
    summary = []
    for metric in metrics:
        values = reference.set_index('player_id')[metric]
        n = int(values.notna().sum())
        constant = n >= 2 and values.nunique() == 1
        scores[metric] = (100 * (values.rank(method='average') - 0.5) / n
                          if n >= 2 else float('nan'))
        summary.append({'Metric': METRICS[metric], 'Valid observations': n,
                        'Status': 'Insufficient data' if n < 2 else
                        'Constant: all valid values receive 50' if constant else 'Available'})
    return scores, pd.DataFrame(summary, columns=['Metric', 'Valid observations', 'Status'])


def radar_issues(selected, metrics, scores, summary):
    issues = []
    if len(metrics) < 3:
        issues.append('Radar requires at least three metrics. Select more metrics or switch to Bars.')
    for metric in metrics:
        missing = selected.loc[selected[metric].isna(), 'player_name'].tolist()
        if missing:
            issues.append(f'{METRICS[metric]} unavailable for {", ".join(missing)}. '
                          'Remove that metric or player, or switch to Bars.')
    insufficient = summary.loc[summary['Valid observations'] < 2, 'Metric'].tolist()
    if insufficient:
        issues.append('Insufficient reference data (at least two valid observations required): '
                      + ', '.join(insufficient) + '. Adjust filters or switch to Bars.')
    if not selected.empty and not set(selected.player_id).issubset(scores.index):
        issues.append('Selected players must belong to the reference population.')
    return issues


def display_value(value, metric):
    if pd.isna(value):
        return 'Unavailable'
    return f'{value:.3f}' if metric.endswith('per90') else f'{int(value):,}'


def actual_values(selected, metrics):
    result = pd.DataFrame({'Player': selected.player_name + ' · ID ' + selected.player_id.astype(str)})
    for metric in metrics:
        result[METRICS[metric]] = selected[metric].map(lambda v: display_value(v, metric))
    return result


def player_label(row):
    return f'{row.player_name} · ID {row.player_id}'


def bar_figure(selected, metric, colors):
    labels = [player_label(row) for row in selected.itertuples()]
    values = [None if pd.isna(v) else float(v) for v in selected[metric]]
    text = [display_value(v, metric) for v in selected[metric]]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation='h',
        marker_color=[colors[int(pid)] for pid in selected.player_id],
        text=text, textposition='outside', cliponaxis=False,
        customdata=text, hovertemplate='%{y}<br>' + METRICS[metric] + ': %{customdata}<extra></extra>',
    ))
    maximum = max([v for v in values if v is not None] or [0])
    fig.update_layout(title=METRICS[metric], height=max(250, 65 * len(selected)),
                      margin=dict(l=10, r=65, t=45, b=40), showlegend=False,
                      xaxis=dict(title=METRICS[metric], range=[0, maximum * 1.25 if maximum else 1]),
                      yaxis=dict(categoryorder='array', categoryarray=labels, autorange='reversed'))
    if not metric.endswith('per90'):
        fig.update_xaxes(tickformat=',d')
    for label, value in zip(labels, values):
        if value is None:
            fig.add_annotation(x=0, y=label, text='Unavailable', showarrow=False, xanchor='left')
    return fig


def radar_figure(selected, metrics, scores, colors):
    labels = [METRICS[m] for m in metrics]
    fig = go.Figure()
    for row in selected.itertuples():
        values = [float(scores.loc[row.player_id, m]) for m in metrics]
        raw = [display_value(getattr(row, m), m) for m in metrics]
        color = colors[int(row.player_id)]
        rgb = ','.join(str(int(color[i:i+2], 16)) for i in (1, 3, 5))
        fig.add_trace(go.Scatterpolar(
            r=values + values[:1], theta=labels + labels[:1],
            name=player_label(row), mode='lines+markers', fill='toself',
            line=dict(color=color), fillcolor=f'rgba({rgb},0.10)',
            customdata=raw + raw[:1],
            hovertemplate='%{theta}<br>Actual: %{customdata}<br>Percentile: %{r:.1f}<extra>%{fullData.name}</extra>',
        ))
    fig.update_layout(height=540, margin=dict(l=70, r=70, t=50, b=100),
                      polar=dict(radialaxis=dict(range=[0, 100], tickvals=[0, 25, 50, 75, 100]),
                                 angularaxis=dict(categoryorder='array', categoryarray=labels)),
                      legend=dict(orientation='h', y=-0.18))
    return fig
