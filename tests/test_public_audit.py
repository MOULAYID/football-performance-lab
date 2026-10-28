import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from scripts.audit_public_data import audit_top5, audit_transfermarkt, download, expected, read_csv


def top5(**updates):
    row = dict(league='ENG-Premier League', season_label='2025/26', team='A', player='Player',
               playing_time_min='90', playing_time_mp='1', fb_gls='0', fb_ast='', us_xg='0.1', ss_goals='1')
    row.update(updates)
    return row


class PublicAuditTests(unittest.TestCase):
    def test_all_25_cells_and_null_not_zero(self):
        result = audit_top5([top5(multi_club='True')])
        self.assertEqual(len(result['matrix']), 25)
        present = [cell for cell in result['matrix'] if cell['rows']]
        self.assertEqual(len(present), 1)
        self.assertEqual(present[0]['missing_fields']['goals'], 0)
        self.assertEqual(present[0]['missing_fields']['assists'], 1)
        self.assertEqual(result['cross_source_counts']['goals_fb_vs_ss']['different'], 1)
        self.assertEqual(result['cross_source_counts']['goals_fb_vs_ss']['different_multi_club_rows'], 1)

    def test_duplicates_invalid_values_and_missing_schema(self):
        result = audit_top5([top5(fb_gls='-1'), top5(fb_gls='oops')])
        self.assertEqual(result['duplicate_name_keys'], 1)
        self.assertEqual(result['invalid_numeric_values'], 2)
        with self.assertRaises(ValueError):
            audit_top5([{'league':'ENG-Premier League'}])

    def test_french_league_size_changes(self):
        self.assertEqual(expected('FRA-Ligue 1',2021), (20,380))
        self.assertEqual(expected('FRA-Ligue 1',2025), (18,306))

    def test_games_appearances_and_orphans(self):
        games = [dict(game_id='1',competition_id='GB1',season='2021',date='2021-08-15',
                      home_club_id='10',away_club_id='20')]
        row = dict(game_id='1',player_id='8',player_club_id='10',minutes_played='90',goals='0',assists='')
        report = audit_transfermarkt(games,[row,row,dict(row,game_id='missing')])
        self.assertEqual(report['duplicate_player_game_keys'],1)
        self.assertEqual(report['orphan_appearance_rows'],1)
        cell = next(c for c in report['matrix'] if c['rows'])
        self.assertEqual(cell['unique_player_ids'],1)
        self.assertEqual(cell['games_without_appearances'],0)
        self.assertFalse(cell['schedule_count_matches_expectation'])

    def test_403_stops_without_retry_or_cache(self):
        with tempfile.TemporaryDirectory() as directory, patch('scripts.audit_public_data.urlopen') as opened:
            opened.side_effect = HTTPError('https://example.com',403,'Forbidden',{},None)
            target = Path(directory)/'sample.csv'
            result = download('https://example.com',target)
            self.assertEqual(result['status'],'blocked')
            self.assertEqual(opened.call_count,1)
            self.assertFalse(target.exists())
            self.assertFalse(target.with_suffix('.csv.part').exists())

    def test_cached_file_uses_no_network(self):
        with tempfile.TemporaryDirectory() as directory, patch('scripts.audit_public_data.urlopen') as opened:
            target = Path(directory)/'sample.csv'
            target.write_text('a,b\n1,2\n',encoding='utf-8')
            result = download('https://example.com',target)
            self.assertEqual(result['status'],'cached')
            opened.assert_not_called()
            self.assertEqual(list(read_csv(target)),[{'a':'1','b':'2'}])
            target.write_text('a,b\n1,2,3\n',encoding='utf-8')
            with self.assertRaises(ValueError):
                list(read_csv(target))


if __name__ == '__main__':
    unittest.main()
