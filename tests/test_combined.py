import unittest
import pandas as pd
from combined import period_totals, period_reference
from comparison import maximum_scores

class PeriodTests(unittest.TestCase):
    def setUp(self):
        self.players=pd.DataFrame([
            dict(player_id=p, player_name=f'Player {p}',position_snapshot='Attack',competition_id=c,season=y,
                 goals=g,assists=a,minutes=m,recorded_appearances=n,
                 goals_per90=999,assists_per90=999,
                 league_matches_with_suspect_coverage=int(y==2022),expected_count_matches=True)
            for p,c,y,g,a,m,n in [(1,'GB1',2021,10,2,900,10),(1,'GB1',2022,1,None,90,1),
                                 (2,'GB1',2022,0,0,0,1),(1,'ES1',2022,50,20,1000,20),
                                 (3,'GB1',2021,2,1,100,2),(3,'GB1',2022,2,1,None,2)]])

    def test_totals_weighted_rates_nulls_and_scope(self):
        before=self.players.copy(deep=True)
        result=period_totals(self.players,'GB1',2021,2022).set_index('player_id')
        self.assertEqual(result.loc[1,'goals'],11)
        self.assertEqual(result.loc[1,'recorded_appearances'],11)
        self.assertEqual(result.loc[1,'minutes'],990)
        self.assertEqual(result.loc[1,'goals_per90'],1)
        self.assertTrue(pd.isna(result.loc[1,'assists']))
        self.assertTrue(pd.isna(result.loc[1,'assists_per90']))
        self.assertEqual(result.loc[2,'goals'],0)
        self.assertTrue(pd.isna(result.loc[2,'goals_per90']))
        self.assertTrue(pd.isna(result.loc[3,'minutes']))
        self.assertTrue(pd.isna(result.loc[3,'goals_per90']))
        pd.testing.assert_frame_equal(before,self.players)

    def test_season_counts_and_filtering(self):
        totals=period_totals(self.players,'GB1',2021,2023)
        one=totals[totals.player_id==1].iloc[0]
        self.assertEqual(one.seasons_recorded,2)
        self.assertEqual(one.seasons_requested,3)
        self.assertEqual(one.absent_seasons,'2023/24')
        self.assertTrue(one.coverage_warning)
        self.assertTrue(period_reference(totals,0,full_seasons=True).empty)
        self.assertEqual(period_reference(totals,0).player_id.tolist(),[1,2])
        self.assertEqual(period_reference(totals,900).player_id.tolist(),[1])
        self.assertTrue(period_reference(totals,0,position='Defender').empty)
        totals=period_totals(self.players,'GB1',2021,2022)
        self.assertEqual(period_reference(totals,0,full_seasons=True).player_id.tolist(),[1])

    def test_empty_and_single_season(self):
        self.assertTrue(period_reference(period_totals(self.players,'FR1',2021,2025),0).empty)
        one=period_totals(self.players,'GB1',2021,2021)
        self.assertEqual(one.iloc[0].goals,10)
        self.assertEqual(one.iloc[0].goals_per90,1)
        self.assertEqual(one.iloc[0].absent_seasons,'None')

    def test_reference_uses_aggregate_population(self):
        ref=period_reference(period_totals(self.players,'GB1',2021,2022),0)
        scores,summary=maximum_scores(ref,['goals','minutes','recorded_appearances'])
        self.assertEqual(scores.loc[1,'goals'],100)
        self.assertEqual(scores.loc[2,'goals'],0)
        self.assertEqual(summary.iloc[0]['Reference maximum'],'11')
        self.assertEqual(scores.loc[[2],'goals'].iloc[0],scores.loc[[1,2],'goals'].loc[2])

    def test_cross_league_transfer_distinct_seasons_and_nulls(self):
        totals=period_totals(self.players,['GB1','ES1'],2021,2022).set_index('player_id')
        row=totals.loc[1]
        self.assertEqual(row.goals,61)
        self.assertEqual(row.minutes,1990)
        self.assertEqual(row.recorded_appearances,31)
        self.assertEqual(row.seasons_recorded,2)
        self.assertEqual(row.absent_seasons,'None')
        self.assertAlmostEqual(row.goals_per90,90*61/1990)
        self.assertTrue(pd.isna(row.assists))
        self.assertTrue(pd.isna(row.assists_per90))
        self.assertEqual(row.league_ids,('ES1','GB1'))
        self.assertEqual(period_reference(totals.reset_index(),0,full_seasons=True).player_id.tolist(),[1])
        single=period_totals(self.players,['GB1','ES1'],2022,2022).set_index('player_id').loc[1]
        self.assertEqual(single.seasons_recorded,1)
        self.assertEqual(single.goals,51)
        pd.testing.assert_frame_equal(period_totals(self.players,'GB1',2021,2022),period_totals(self.players,['GB1'],2021,2022))

    def test_breakdown_and_known_excluded_records(self):
        from combined import league_breakdown, excluded_records
        excluded=excluded_records(self.players,[1],['GB1'],2021,2022)
        self.assertEqual(excluded.competition_id.tolist(),['ES1'])
        self.assertEqual(excluded.season.tolist(),[2022])
        self.assertTrue(excluded_records(self.players,[1],['GB1','ES1'],2021,2022).empty)
        self.assertTrue(excluded_records(self.players,[1],['GB1'],2021,2021).empty)
        detail=league_breakdown(self.players,[1],['GB1','ES1'],2021,2022).set_index('competition_id')
        self.assertEqual(detail.loc['GB1','goals'],11)
        self.assertEqual(detail.loc['ES1','goals'],50)
        self.assertTrue(pd.isna(detail.loc['GB1','assists']))
        self.assertTrue(detail.loc['ES1','coverage_warning'])

    def test_empty_leagues_and_duplicate_aggregate_rejected(self):
        self.assertTrue(period_totals(self.players,[],2021,2025).empty)
        duplicated=pd.concat([self.players,self.players.iloc[[0]]],ignore_index=True)
        with self.assertRaisesRegex(ValueError,'one aggregate'):
            period_totals(duplicated,['GB1'],2021,2025)

    def test_union_reference_maximum_and_every_season(self):
        more=self.players.copy()
        more.loc[(more.player_id==1)&(more.competition_id=='GB1')&(more.season==2022),'player_id']=4
        ref=period_reference(period_totals(more,['GB1','ES1'],2021,2022),0,full_seasons=True)
        self.assertEqual(ref.player_id.tolist(),[1])  # GB1 in 2021 and ES1 in 2022.
        ref=period_reference(period_totals(self.players,['GB1','ES1'],2021,2022),0)
        scores,summary=maximum_scores(ref,['goals'])
        self.assertEqual(summary.iloc[0]['Reference maximum'],'61')
        self.assertEqual(scores.loc[2,'goals'],0)
