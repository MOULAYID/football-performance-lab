import unittest

import pandas as pd

from comparison import (COLORS, METRICS, actual_values, bar_figure,
                        percentile_scores, radar_figure, radar_issues,
                        reference_population)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.players = pd.DataFrame({
            'player_id': [1, 2, 3, 4, 5], 'player_name': list('ABCDE'),
            'competition_id': ['GB1', 'GB1', 'GB1', 'ES1', 'GB1'],
            'season': [2024, 2024, 2024, 2024, 2023],
            'position_snapshot': ['Attack', 'Attack', 'Defender', 'Attack', 'Attack'],
            'minutes': [1000, 500, 1000, 1000, 1000],
            'goals': [0, 2, 2, 9, 9], 'assists': [None, 0, 1, 2, 3],
            'recorded_appearances': [10, 10, 10, 10, 10],
        })

    def test_reference_filters_and_unknown_minutes(self):
        self.assertEqual(reference_population(self.players, 'GB1', 2024, 900).player_id.tolist(), [1, 3])
        self.assertEqual(reference_population(self.players, 'GB1', 2024, 900, 'Attack').player_id.tolist(), [1])
        self.players.loc[0, 'minutes'] = None
        self.assertEqual(reference_population(self.players, 'GB1', 2024, 0).player_id.tolist(), [2, 3])

    def test_midrank_ties_missing_and_constants(self):
        ref = self.players.iloc[:3]
        scores, summary = percentile_scores(ref, ['goals', 'assists', 'recorded_appearances'])
        self.assertAlmostEqual(scores.loc[1, 'goals'], 100 / 6)
        self.assertAlmostEqual(scores.loc[2, 'goals'], 200 / 3)
        self.assertEqual(scores.loc[2, 'goals'], scores.loc[3, 'goals'])
        self.assertTrue(pd.isna(scores.loc[1, 'assists']))
        self.assertEqual(scores.loc[2, 'assists'], 25)
        self.assertEqual(scores.loc[3, 'assists'], 75)
        self.assertEqual(scores.recorded_appearances.tolist(), [50, 50, 50])
        self.assertEqual(summary['Valid observations'].tolist(), [3, 2, 3])

    def test_insufficient_empty_and_missing_radar(self):
        metrics = ['goals', 'assists', 'recorded_appearances']
        for ref in [self.players.iloc[:0], self.players.iloc[:1]]:
            scores, summary = percentile_scores(ref, metrics)
            self.assertTrue(scores.isna().all().all())
            self.assertTrue(any('Insufficient' in x for x in radar_issues(ref, metrics, scores, summary)))
        scores, summary = percentile_scores(self.players, metrics)
        self.assertTrue(any('unavailable for A' in x for x in radar_issues(self.players.iloc[:1], metrics, scores, summary)))
        scores, summary = percentile_scores(self.players, [])
        self.assertTrue(any('at least three' in x for x in radar_issues(self.players.iloc[:1], [], scores, summary)))
        self.assertEqual(actual_values(self.players.iloc[:1], []).columns.tolist(), ['Player'])

    def test_actual_values_and_chart_contracts(self):
        selected = self.players.iloc[:3]
        colors = dict(zip(selected.player_id, COLORS))
        values = actual_values(selected, ['goals', 'assists', 'recorded_appearances'])
        self.assertEqual(values['Goals'].tolist(), ['0', '2', '2'])
        self.assertEqual(values['Assists'].tolist(), ['Unavailable', '0', '1'])
        self.assertEqual(values['Appearances'].tolist(), ['10', '10', '10'])
        self.assertEqual(METRICS['recorded_appearances'], 'Appearances')
        bar = bar_figure(selected, 'assists', colors)
        self.assertEqual(list(bar.data[0].x), [None, 0, 1])
        self.assertEqual(bar.layout.xaxis.range[0], 0)
        self.assertEqual(bar.layout.annotations[0].text, 'Unavailable')
        metrics = ['goals', 'minutes', 'recorded_appearances']
        scores, summary = percentile_scores(selected, metrics)
        self.assertFalse(radar_issues(selected, metrics, scores, summary))
        radar = radar_figure(selected, metrics, scores, colors)
        for index, trace in enumerate(radar.data):
            self.assertEqual(trace.line.color, bar.data[0].marker.color[index])
            self.assertEqual(trace.r[0], trace.r[-1])
            self.assertEqual(trace.customdata[2], '10')
        self.assertEqual(tuple(radar.layout.polar.radialaxis.range), (0, 100))
        bar.to_json()
        radar.to_json()

    def test_scores_independent_of_search_and_selection(self):
        ref = reference_population(self.players, 'GB1', 2024, 0)
        scores, _ = percentile_scores(ref, ['goals'])
        # Search restricts candidates only, never the population passed to scoring.
        candidate = ref[ref.player_name.str.contains('B')]
        self.assertEqual(scores.loc[candidate.player_id.iloc[0], 'goals'], scores.loc[2, 'goals'])
        first = scores.loc[[2], 'goals']
        second = scores.loc[[2, 3], 'goals']
        self.assertEqual(first.loc[2], second.loc[2])
