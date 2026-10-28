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

    def test_single_season_unified_comparison(self):
        app = AppTest.from_file(str(APP), default_timeout=15).run()
        self.assertEqual([tab.label for tab in app.tabs], ['Players','Compare players','Performance over time','Data & methodology'])
        self.assertEqual(app.select_slider(key='period_range').value, (2025,2025))
        app.select_slider(key='period_range').set_value((2024,2024)).run()
        app.number_input(key='period_minutes').set_value(0).run()
        app.multiselect(key='period_players').set_value([1,2]).run()
        tab=app.tabs[1]
        self.assertFalse(app.exception)
        self.assertEqual(tab.dataframe[1].value['Appearances'].tolist(),['2','1'])
        self.assertEqual(tab.dataframe[1].value['Assists'].tolist(),['Unavailable','0'])
        self.assertTrue(any('Period coverage warning' in w.value for w in tab.warning))
        detail=tab.dataframe[2].value
        self.assertEqual(sum(int(x) for x in detail.loc[detail.Player=='Transfer Player','Appearances']),2)
        self.assertFalse(any(x.key=='period_full' for x in app.checkbox))
        app.radio(key='period_chart').set_value('Radar').run()
        self.assertTrue(any('unavailable' in w.value for w in app.tabs[1].warning))
        self.assertEqual(len(app.tabs[1].get('plotly_chart')),0)
        app.multiselect(key='period_metrics').set_value(['goals','minutes']).run()
        self.assertTrue(any('at least three' in w.value for w in app.tabs[1].warning))
        app.multiselect(key='period_metrics').set_value(['goals','minutes','recorded_appearances']).run()
        self.assertEqual(len(app.tabs[1].get('plotly_chart')),1)
        colors=app.session_state['period_colors']
        app.select_slider(key='period_range').set_value((2021,2025)).run()
        self.assertEqual(app.multiselect(key='period_players').value,[1,2])
        self.assertEqual(app.multiselect(key='period_metrics').value,['goals','minutes','recorded_appearances'])
        self.assertEqual(app.radio(key='period_chart').value,'Radar')
        self.assertEqual(app.session_state['period_colors'],colors)
        app.select_slider(key='period_range').set_value((2024,2024)).run()
        self.assertEqual(app.multiselect(key='period_players').value,[1,2])
        app.selectbox(key='period_position').set_value('Attack').run()
        self.assertTrue(any('Insufficient reference data' in w.value for w in app.tabs[1].warning))
        self.assertFalse(app.exception)

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

    def test_combined_period_controls_and_charts(self):
        app = AppTest.from_file(str(APP), default_timeout=15).run()
        app.select_slider(key='period_range').set_value((2021,2025)).run()
        app.number_input(key='period_minutes').set_value(0).run()
        app.multiselect(key='period_players').set_value([1,2]).run()
        self.assertFalse(app.exception)
        tab=app.tabs[1]
        self.assertEqual(len(tab.get('plotly_chart')),5)
        self.assertTrue(any('Incomplete season coverage' in w.value for w in tab.warning))
        self.assertEqual(tab.dataframe[0].value['Seasons with records'].tolist(),[1,1])
        self.assertEqual(tab.dataframe[1].value['Appearances'].tolist(),['2','1'])
        self.assertEqual(tab.dataframe[1].value['Assists'].tolist(),['Unavailable','0'])
        app.multiselect(key='period_metrics').set_value(['goals','minutes','recorded_appearances']).run()
        app.radio(key='period_chart').set_value('Radar').run()
        self.assertFalse(app.exception)
        before=json.loads(app.tabs[1].get('plotly_chart')[0].proto.spec)['data'][0]['r']
        app.text_input(key='period_search').set_value('Transfer').run()
        self.assertEqual(app.multiselect(key='period_players').value,[1])
        after=json.loads(app.tabs[1].get('plotly_chart')[0].proto.spec)['data'][0]['r']
        self.assertEqual(before,after)
        app.text_input(key='search').set_value('nobody').run()
        self.assertEqual(app.multiselect(key='period_players').value,[1])
        app.radio(key='period_chart').set_value('Bars').run()
        self.assertEqual(len(app.tabs[1].get('plotly_chart')),3)
        app.multiselect(key='period_metrics').set_value([]).run()
        self.assertEqual(len(app.tabs[1].get('plotly_chart')),0)
        app.checkbox(key='period_full').set_value(True).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.multiselect(key='period_players').value,[])
        app.select_slider(key='period_range').set_value((2024,2024)).run()
        app.multiselect(key='period_players').set_value([1]).run()
        self.assertEqual(app.tabs[1].dataframe[0].value['Seasons selected'].tolist(),[1])

    def test_missing_database(self):
        with patch.dict(os.environ, {'FOOTBALL_DB_PATH': str(self.fixture.root / 'absent.duckdb')}):
            app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        self.assertIn('Build the local database', app.info[0].value)

if __name__ == '__main__':
    unittest.main()
