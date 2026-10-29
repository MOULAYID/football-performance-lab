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
        app.session_state['period_search'] = 'Transfer'  # Ignore stale pre-upgrade search.
        app.run()
        self.assertEqual(app.multiselect(key='period_players').value,[1,2])
        after=json.loads(app.tabs[1].get('plotly_chart')[0].proto.spec)['data'][0]['r']
        self.assertEqual(before,after)
        app.text_input(key='search').set_value('nobody').run()
        self.assertEqual(app.multiselect(key='period_players').value,[1,2])
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

    def test_cross_league_controls_breakdowns_and_exclusions(self):
        import pandas as pd
        for name, extra in {
            'games': {'game_id':4,'competition_id':'ES1','season':2024,'date':'2024-11-01','home_club_id':10,'away_club_id':20,'home_club_goals':1,'away_club_goals':0},
            'appearances': {'player_id':1,'game_id':4,'player_club_id':10,'minutes_played':90,'goals':1,'assists':0},
            'competitions': {'competition_id':'ES1','name':'La Liga'},
        }.items():
            path=self.fixture.root/(name+'.csv')
            frame=pd.read_csv(path)
            pd.concat([frame,pd.DataFrame([extra])],ignore_index=True).to_csv(path,index=False)
        build_database(self.fixture.root,self.fixture.output)
        app=AppTest.from_file(str(APP),default_timeout=15).run()
        self.assertEqual(app.multiselect(key='period_leagues').value,['GB1'])
        app.select_slider(key='period_range').set_value((2024,2024)).run()
        app.number_input(key='period_minutes').set_value(0).run()
        app.multiselect(key='period_players').set_value([1,2]).run()
        self.assertTrue(any('Known excluded records' in w.value for w in app.tabs[1].warning))
        colors=app.session_state['period_colors']
        app.multiselect(key='period_leagues').set_value(['GB1','ES1']).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.multiselect(key='period_players').value,[1,2])
        self.assertEqual(app.session_state['period_colors'],colors)
        self.assertTrue(any('La Liga' in x for x in app.multiselect(key='period_players').options))
        self.assertEqual(app.tabs[1].dataframe[1].value['Goals'].tolist(),['3','0'])
        self.assertEqual(app.tabs[1].dataframe[0].value['Seasons with records'].tolist(),[1,1])
        self.assertIn('League',app.tabs[1].dataframe[2].value.columns)
        self.assertEqual(set(app.tabs[1].dataframe[3].value.League),{'Premier League','La Liga'})
        self.assertFalse(any('Known excluded records' in w.value for w in app.tabs[1].warning))
        app.multiselect(key='period_metrics').set_value(['goals','minutes','recorded_appearances']).run()
        app.radio(key='period_chart').set_value('Radar').run()
        before=json.loads(app.tabs[1].get('plotly_chart')[0].proto.spec)['data'][0]['r']
        app.session_state['period_search'] = 'Transfer'  # Ignore stale pre-upgrade search.
        app.run()
        self.assertEqual(before,json.loads(app.tabs[1].get('plotly_chart')[0].proto.spec)['data'][0]['r'])
        app.radio(key='period_chart').set_value('Bars').run()
        self.assertEqual(app.session_state['period_colors'][1],colors[1])
        app.multiselect(key='period_leagues').set_value([]).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.multiselect(key='period_players').value,[])
        self.assertEqual(len(app.tabs[1].get('plotly_chart')),0)
        self.assertTrue(any('Select at least one league' in x.value for x in app.tabs[1].info))
        self.assertEqual(app.multiselect(key='period_metrics').value,['goals','minutes','recorded_appearances'])
        app.multiselect(key='period_leagues').set_value(['ES1']).run()
        app.multiselect(key='period_players').set_value([1]).run()
        self.assertFalse(app.exception)
        app.multiselect(key='period_leagues').set_value(['FR1']).run()
        self.assertEqual(app.multiselect(key='period_players').value,[])

    def test_player_filters_are_local_readable_and_recover_from_empty_results(self):
        app = AppTest.from_file(str(APP), default_timeout=15).run()
        self.assertEqual(len(app.sidebar.selectbox), 0)
        self.assertEqual(len(app.sidebar.number_input), 0)
        self.assertFalse(any(t.key == 'period_search' for t in app.text_input))
        app.selectbox(key='season').set_value(2024).run()
        app.number_input(key='minutes').set_value(0).run()
        config = json.loads(app.tabs[0].dataframe[0].proto.columns)
        self.assertEqual(config['recorded_appearances']['label'], 'Appearances')
        self.assertIn('substitute appearances', config['recorded_appearances']['help'])
        app.number_input(key='min_goals').set_value(1).run()
        self.assertEqual(app.tabs[0].dataframe[0].value.player_name.tolist(), ['Transfer Player'])
        app.number_input(key='min_assists').set_value(0).run()
        self.assertTrue(any('No players match' in x.value for x in app.tabs[0].info))
        app.number_input(key='min_goals').set_value(None).run()
        app.number_input(key='min_assists').set_value(None).run()
        app.text_input(key='search').set_value('no such player').run()
        self.assertTrue(any('No players match' in x.value for x in app.tabs[0].info))
        app.text_input(key='search').set_value('').run()
        self.assertEqual(len(app.tabs[0].dataframe[0].value), 2)
        self.assertFalse(app.exception)

    def test_history_changes_are_optional_without_losing_actual_values(self):
        app = AppTest.from_file(str(APP), default_timeout=15).run()
        app.selectbox(key='history_player').set_value(1).run()
        original = app.tabs[2].dataframe[0].value
        self.assertFalse(any(c.endswith(' change') for c in original))
        app.checkbox(key='history_show_changes').set_value(True).run()
        expanded = app.tabs[2].dataframe[0].value
        self.assertIn('Goals change', expanded)
        self.assertTrue(expanded[original.columns].equals(original))
        self.assertIn('Historical clubs by season', [e.label for e in app.tabs[2].expander])
        self.assertFalse(app.exception)

    def test_missing_database(self):
        with patch.dict(os.environ, {'FOOTBALL_DB_PATH': str(self.fixture.root / 'absent.duckdb')}):
            app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        self.assertIn('Build the local database', app.info[0].value)

if __name__ == '__main__':
    unittest.main()
