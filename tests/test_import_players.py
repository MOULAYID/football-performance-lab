import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.check_access import AuditError
from scripts.import_players import normalize, run, validate_page


def page(number=1, total=1, pid=1):
    stat = {'league': {'id': 39, 'season': 2024}, 'team': {'id': 10, 'name': 'A'},
            'games': {'minutes': 90, 'appearences': 1, 'position': 'Attacker'},
            'goals': {'total': 0, 'assists': None}}
    return {'paging': {'current': number, 'total': total},
            'response': [{'player': {'id': pid, 'name': 'Player'}, 'statistics': [stat]}]}


class ImportTests(unittest.TestCase):
    def test_team_stints_and_nulls_preserved(self):
        data = page()
        second = copy.deepcopy(data['response'][0]['statistics'][0])
        second['team'] = {'id': 11, 'name': 'B'}
        data['response'][0]['statistics'].append(second)
        rows, report = normalize([data], 39, 2024)
        self.assertEqual(len(rows), 2)
        self.assertEqual(report['unique_players'], 1)
        self.assertEqual(rows[0]['goals'], 0)
        self.assertIsNone(rows[0]['assists'])

    def test_shifted_pagination_rejected(self):
        with self.assertRaises(AuditError):
            validate_page(page(2, 3), 2, 2)
        with self.assertRaises(AuditError):
            normalize([page(), page()], 39, 2024)

    def test_conflicting_stint_rejected(self):
        data = page()
        second = copy.deepcopy(data['response'][0]['statistics'][0])
        second['games']['minutes'] = 180
        data['response'][0]['statistics'].append(second)
        with self.assertRaises(AuditError):
            normalize([data], 39, 2024)

    def test_pause_resume_and_repeat_without_network(self):
        args = argparse.Namespace(league=39, season=2024, snapshot='test', max_requests=1, delay=7)
        with tempfile.TemporaryDirectory() as directory, patch('scripts.import_players.ROOT', Path(directory)), \
                patch.dict('os.environ', {'API_FOOTBALL_KEY': 'test-secret'}), \
                patch('scripts.import_players.fetch', side_effect=[page(1, 2, 1), page(2, 2, 2)]) as fetch, \
                patch('builtins.print'):
            self.assertEqual(run(args), 0)
            self.assertFalse((Path(directory) / 'data/processed').exists())
            self.assertEqual(run(args), 0)
            self.assertEqual(run(args), 0)
            self.assertEqual(fetch.call_count, 2)
            report = json.loads(next(Path(directory).rglob('quality_report.json')).read_text())
            self.assertEqual(report['unique_players'], 2)
            for file in Path(directory).rglob('*.json'):
                self.assertNotIn('test-secret', file.read_text())


if __name__ == '__main__':
    unittest.main()
