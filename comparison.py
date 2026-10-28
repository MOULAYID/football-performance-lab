"""Comparison filtering, maximum-relative scaling and Python-only Plotly figures."""
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


def maximum_scores(reference, metrics):
    """Scale nonnegative metrics against the full reference maximum.

    Missing values stay missing. All-zero metrics have no defined denominator
    and block the radar. Positive constants receive 100 with an explicit warning.
    """
    scores = pd.DataFrame(index=reference.player_id)
    summary = []
    for metric in metrics:
        values = reference.set_index('player_id')[metric]
        n = int(values.notna().sum())
        maximum = values.max()
        constant = n >= 2 and values.nunique() == 1
        scores[metric] = (100 * values / maximum
                          if n >= 2 and maximum > 0 else float('nan'))
        summary.append({'Metric': METRICS[metric], 'Valid observations': n,
                        'Reference maximum': display_value(maximum, metric),
                        'Status': 'Insufficient data' if n < 2 else
                        'Zero maximum: scaling unavailable' if maximum == 0 else
                        'Constant: all valid values receive 100' if constant else 'Available'})
    return scores, pd.DataFrame(summary, columns=['Metric', 'Valid observations', 'Reference maximum', 'Status'])


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
    zero_max = summary.loc[summary.Status.str.startswith('Zero maximum'), 'Metric'].tolist()
    if zero_max:
        issues.append('Zero reference maximum: ' + ', '.join(zero_max) +
                      '. All recorded values are zero; remove these metrics or switch to Bars.')
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
            hovertemplate='%{theta}<br>Actual: %{customdata}<br>Reference maximum share: %{r:.1f}%<extra>%{fullData.name}</extra>',
        ))
    # Own the complete panel palette; Streamlit's theme otherwise leaves the
    # polar background white while changing text to white in dark mode.
    fig.update_layout(
        template='plotly_dark', height=570,
        paper_bgcolor='#111827', plot_bgcolor='#111827',
        font=dict(color='#F3F4F6', size=14),
        margin=dict(l=90, r=90, t=65, b=95),
        title=dict(text='Percentage of reference maximum', x=0.5, xanchor='center'),
        polar=dict(bgcolor='#111827',
                   radialaxis=dict(range=[0, 100], tickvals=[0, 25, 50, 75, 100],
                                   ticksuffix='%', angle=15, tickfont=dict(color='#D1D5DB', size=12),
                                   gridcolor='#4B5563', linecolor='#6B7280'),
                   angularaxis=dict(categoryorder='array', categoryarray=labels,
                                    tickfont=dict(color='#F3F4F6', size=14),
                                    gridcolor='#4B5563', linecolor='#6B7280')),
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.12, yanchor='top',
                    font=dict(color='#F3F4F6', size=13)),
        hoverlabel=dict(bgcolor='#1F2937', font_color='#F9FAFB'),
    )
    return fig
