import unittest
import pandas as pd
from performance import player_history, history_table, trend_figure

LEAGUES = {'GB1': 'Premier League', 'ES1': 'La Liga'}

class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.players = pd.DataFrame([
            dict(player_id=1, season=y, competition_id=c, goals=g, assists=0,
                 minutes=m, recorded_appearances=10, goals_per90=90*g/m if m else None,
                 assists_per90=0 if m else None, league_matches_with_suspect_coverage=1 if y==2024 else 0,
                 expected_count_matches=True)
            for y,c,g,m in [(2021,'GB1',0,900),(2022,'GB1',10,1000),(2024,'GB1',5,500),
                            (2024,'ES1',3,300),(2025,'ES1',0,0)]])
        self.stints = pd.DataFrame([dict(player_id=1,season=r.season,competition_id=r.competition_id,club_name_snapshot='Club A') for r in self.players.itertuples()])

    def test_gaps_split_leagues_and_no_mutation(self):
        before = self.players.copy(deep=True)
        history = player_history(self.players,self.stints,1,2021,2025)
        self.assertEqual(len(history),6)
        self.assertTrue(history.loc[history.season==2023,'goals'].isna().all())
        self.assertEqual(len(history[history.season==2024]),2)
        self.assertEqual(history.loc[history.season==2021,'goals'].iloc[0],0)
        self.assertTrue(history.loc[history.season==2024,'status'].str.startswith('Coverage warning').all())
        pd.testing.assert_frame_equal(before,self.players)
        fig=trend_figure(history,'goals',LEAGUES)
        self.assertEqual(list(fig.data[0].y),[None,None,None,3,0])
        self.assertEqual(list(fig.data[1].y),[0,10,None,5,None])
        self.assertFalse(fig.data[0].connectgaps)
        fig.to_json()

    def test_changes_zero_baseline_and_transfer_guard(self):
        history=player_history(self.players,self.stints,1,2021,2025)
        table=history_table(history,['goals','goals_per90'],LEAGUES)
        self.assertEqual(table.iloc[1]['Goals change'],'+10')
        self.assertEqual(table.iloc[1]['Goals change %'],'Unavailable')
        self.assertTrue((table.iloc[2:]['Goals change']=='Unavailable').all())
        self.assertEqual(table.iloc[-1]['Goals per 90'],'Unavailable')
        self.players.loc[self.players.season==2021,'goals']=5
        table=history_table(player_history(self.players,self.stints,1,2021,2022),['goals'],LEAGUES)
        self.assertEqual(table.iloc[1]['Goals change %'],'+100.0%')

    def test_empty_range_and_same_league_club_names(self):
        extra=self.stints.iloc[[0]].copy()
        extra['club_name_snapshot']='Club B'
        history=player_history(self.players,pd.concat([self.stints,extra]),1,2021,2021)
        self.assertEqual(history.iloc[0].clubs,'Club A, Club B')
        self.assertEqual(history.iloc[0].recorded_appearances,10)
        absent=player_history(self.players,self.stints,999,2021,2025)
        self.assertEqual(len(absent),5)
        self.assertTrue(absent.goals.isna().all())
        self.assertEqual(len(history_table(absent,[],LEAGUES)),5)
