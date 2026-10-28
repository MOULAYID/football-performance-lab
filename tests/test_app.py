import os
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
import test_database
from scripts.build_database import build_database

APP = Path(__file__).resolve().parents[1] / 'app.py'

class ExplorerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_database.DatabaseTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        build_database(self.fixture.root, self.fixture.output)
        self.env = patch.dict(os.environ, {'FOOTBALL_DB_PATH': str(self.fixture.output)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_filters_comparison_and_coverage(self):
        app = AppTest.from_file(str(APP), default_timeout=15).run()
        app.selectbox(key='season').set_value(2024).run()
        app.number_input(key='minutes').set_value(0).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('lack appearances' in w.value for w in app.warning))
        app.multiselect(key='players').set_value([1, 2]).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[1].value), 2)
        values = app.dataframe[1].value
        self.assertEqual(values['Appearances'].tolist(), ['2', '1'])
        self.assertEqual(values['Assists'].tolist(), ['Unavailable', '0'])
        stints = app.dataframe[2].value
        self.assertEqual(sum(int(x) for x in stints.loc[stints.Player == 'Transfer Player', 'Appearances']), 2)
        app.multiselect(key='comparison_metrics').set_value(['goals', 'recorded_appearances', 'minutes']).run()
        app.radio(key='chart_type').set_value('Radar').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.multiselect(key='players').value, [1, 2])
        self.assertEqual(len(app.get('plotly_chart')), 1)
        self.assertEqual(app.dataframe[1].value['Valid observations'].tolist(), [2, 2, 2])
        colors = app.session_state['comparison_colors']
        app.radio(key='chart_type').set_value('Bars').run()
        self.assertEqual(len(app.get('plotly_chart')), 3)
        self.assertEqual(app.session_state['comparison_colors'], colors)
        self.assertEqual(app.multiselect(key='comparison_metrics').value, ['goals', 'recorded_appearances', 'minutes'])
        app.multiselect(key='comparison_metrics').set_value([]).run()
        self.assertTrue(any('Select one or more' in x.value for x in app.info))
        self.assertEqual(len(app.get('plotly_chart')), 0)
        app.text_input(key='search').set_value('no such player').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('No players' in x.value for x in app.info))

    def test_radar_guardrails_and_search_population(self):
        app = AppTest.from_file(str(APP), default_timeout=15).run()
        app.selectbox(key='season').set_value(2024).run()
        app.number_input(key='minutes').set_value(0).run()
        app.multiselect(key='players').set_value([1, 2]).run()
        app.radio(key='chart_type').set_value('Radar').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('unavailable' in w.value for w in app.warning))
        self.assertEqual(len(app.get('plotly_chart')), 0)
        self.assertTrue(any('Actual values' == h.value for h in app.subheader))
        app.multiselect(key='comparison_metrics').set_value(['goals', 'minutes']).run()
        self.assertTrue(any('at least three' in w.value for w in app.warning))
        app.multiselect(key='comparison_metrics').set_value(['goals', 'minutes', 'recorded_appearances']).run()
        before = json.loads(app.get('plotly_chart')[0].proto.spec)['data'][0]['r']
        app.text_input(key='search').set_value('Transfer').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.multiselect(key='players').value, [1])
        self.assertEqual(app.dataframe[1].value['Valid observations'].tolist(), [2, 2, 2])
        after = json.loads(app.get('plotly_chart')[0].proto.spec)['data'][0]['r']
        self.assertEqual(before, after)
        self.assertTrue(any('lack appearances' in w.value for w in app.warning))
        app.selectbox(key='position').set_value('Attack').run()
        self.assertTrue(any('Insufficient reference data' in w.value for w in app.warning))
        self.assertEqual(len(app.get('plotly_chart')), 0)

    def test_history_independent_controls_and_missing_seasons(self):
        app = AppTest.from_file(str(APP), default_timeout=15).run()
        app.selectbox(key='history_player').set_value(1).run()
        self.assertFalse(app.exception)
        tab = app.tabs[2]
        self.assertEqual(len(tab.get('plotly_chart')), 3)  # Assists missing in fixture.
        table = tab.dataframe[0].value
        self.assertEqual(table['Season'].tolist(), ['2021/22','2022/23','2023/24','2024/25','2025/26'])
        self.assertEqual(table['Goals'].tolist(), ['Unavailable','Unavailable','Unavailable','2','Unavailable'])
        self.assertTrue(any('Historical coverage warning' in w.value for w in tab.warning))
        app.text_input(key='search').set_value('nobody').run()
        app.selectbox(key='league').set_value('ES1').run()
        self.assertEqual(app.selectbox(key='history_player').value, 1)
        self.assertTrue(app.tabs[2].dataframe[0].value.equals(table))
        app.select_slider(key='history_range').set_value((2024,2024)).run()
        self.assertEqual(len(app.tabs[2].dataframe[0].value),1)
        app.multiselect(key='history_metrics').set_value([]).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.tabs[2].get('plotly_chart')),0)
        self.assertTrue(any('Select at least one' in x.value for x in app.tabs[2].info))

    def test_missing_database(self):
        with patch.dict(os.environ, {'FOOTBALL_DB_PATH': str(self.fixture.root / 'absent.duckdb')}):
            app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        self.assertIn('Build the local database', app.info[0].value)

if __name__ == '__main__':
    unittest.main()
