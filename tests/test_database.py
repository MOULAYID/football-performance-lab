import csv
from pathlib import Path
import tempfile
import unittest

import duckdb
from scripts.build_database import build_database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / 'football.duckdb'
        self.write('games', ['game_id','competition_id','season','date','home_club_id','away_club_id','home_club_goals','away_club_goals'],
                   [[1,'GB1',2024,'2024-08-01',10,20,1,0],[2,'GB1',2024,'2024-09-01',10,20,0,1],[3,'GB1',2024,'2024-10-01',10,20,0,0]])
        self.appearances = [[1,1,10,90,1,0],[1,2,20,45,1,None],[2,1,20,0,0,0]]
        self.write_appearances()
        self.write('players',['player_id','name','date_of_birth','country_of_citizenship','position','sub_position'],
                   [[1,'Transfer Player','2000-01-01','France','Attack','Striker'],[2,'Zero Minutes','2001-01-01','Spain','Defender','Centre-Back']])
        self.write('clubs',['club_id','name'],[[10,'Club A'],[20,'Club B']])
        self.write('competitions',['competition_id','name'],[['GB1','Premier League']])

    def write(self, name, header, rows):
        with (self.root / (name+'.csv')).open('w',newline='',encoding='utf-8') as f:
            writer=csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

    def write_appearances(self):
        self.write('appearances',['player_id','game_id','player_club_id','minutes_played','goals','assists'],self.appearances)

    def test_transfer_totals_nulls_and_coverage(self):
        report=build_database(self.root,self.output)
        with duckdb.connect(str(self.output),read_only=True) as con:
            row=con.execute('SELECT clubs_played_for,recorded_appearances,minutes,goals,assists,goals_per90 FROM player_season WHERE player_id=1').fetchone()
            self.assertEqual(row[:5],(2,2,135,2,None))
            self.assertAlmostEqual(row[5],4/3)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM player_club_season WHERE player_id=1').fetchone()[0],2)
            self.assertIsNone(con.execute('SELECT goals_per90 FROM player_season WHERE player_id=2').fetchone()[0])
            self.assertEqual(con.execute('SELECT game_id FROM match_coverage WHERE missing_appearances').fetchall(),[(3,)])
            self.assertEqual(con.execute('SELECT COUNT(*) FROM league_season_coverage').fetchone()[0],25)
        self.assertEqual(report['counts']['player_match_stats'],3)
        again=build_database(self.root,self.output)
        self.assertEqual(again['counts'],report['counts'])

    def test_duplicate_rejected_and_previous_database_preserved(self):
        build_database(self.root,self.output)
        before=self.output.read_bytes()
        self.appearances.append(self.appearances[0])
        self.write_appearances()
        with self.assertRaises(duckdb.Error):
            build_database(self.root,self.output)
        self.assertEqual(self.output.read_bytes(),before)

    def test_wrong_historical_club_rejected(self):
        self.appearances[0][2]=999
        self.write_appearances()
        with self.assertRaisesRegex(ValueError,'wrong_historical_club'):
            build_database(self.root,self.output)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
