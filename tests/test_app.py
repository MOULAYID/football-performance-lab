import os
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
        app.selectbox(key='metric').set_value('goals_per90').run()
        self.assertTrue(any('omitted' in x.value for x in app.info))
        app.text_input(key='search').set_value('no such player').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('No players' in x.value for x in app.info))

    def test_missing_database(self):
        with patch.dict(os.environ, {'FOOTBALL_DB_PATH': str(self.fixture.root / 'absent.duckdb')}):
            app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        self.assertIn('Build the local database', app.info[0].value)

if __name__ == '__main__':
    unittest.main()
