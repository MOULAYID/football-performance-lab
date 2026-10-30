import unittest
from unittest.mock import patch
from scripts.check_access import AuditError, error_reason, fetch, summarize_players


class AuditTests(unittest.TestCase):
    def test_plan_reason_is_visible_but_key_and_account_are_not(self):
        result = error_reason({'errors': {'plan': 'Season unavailable for SECRET'},
                               'account': {'email': 'private@example.com'}}, 'SECRET')
        self.assertIn('Season unavailable', result)
        self.assertNotIn('SECRET', result)
        self.assertNotIn('private@example.com', result)

    def test_escaped_key_is_redacted(self):
        self.assertNotIn('sensitive', error_reason({'message': 'sensitive"key'}, 'sensitive"key'))

    def test_zero_is_not_missing_and_other_seasons_are_excluded(self):
        stats = {'league': {'id': 39, 'season': 2023},
                 'games': {'minutes': 0, 'position': 'Attacker'},
                 'goals': {'total': 0, 'assists': None}}
        other = dict(stats, league={'id': 39, 'season': 2022})
        result = summarize_players({'response': [{'player': {'id': 1},
                                                  'statistics': [stats, other]}]}, 39, 2023)
        self.assertEqual(result['matching_stat_rows'], 1)
        self.assertEqual(result['missing_fields'], {'minutes': 0, 'position': 0, 'goals': 0, 'assists': 1})

    def test_http_200_provider_errors_are_rejected_without_echoing_secrets(self):
        with patch('scripts.check_access.urlopen') as opened:
            opened.return_value.__enter__.return_value.read.return_value = b'{"errors":{"token":"SECRET"}}'
            with self.assertRaises(AuditError) as caught:
                fetch('https://example.com', '/test', 'key', 'SECRET')
        self.assertNotIn('SECRET', str(caught.exception))

    def test_empty_sample_is_not_invented(self):
        result = summarize_players({'response': []}, 39, 2023)
        self.assertEqual(result['player_records'], 0)
        self.assertEqual(result['matching_stat_rows'], 0)


if __name__ == '__main__':
    unittest.main()
