from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cloud_bootstrap import ensure_database


class CloudBootstrapTests(unittest.TestCase):
    def test_existing_database_never_downloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'existing.duckdb'
            path.write_bytes(b'existing')
            with patch('cloud_bootstrap.download') as download:
                self.assertEqual(ensure_database(tmp,path),path)
                download.assert_not_called()

    def test_denial_stops_before_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'new.duckdb'
            with patch('cloud_bootstrap.download',return_value={'status':'blocked'}) as download, patch('cloud_bootstrap.build_database') as build:
                with self.assertRaisesRegex(RuntimeError,'games: blocked'):
                    ensure_database(tmp,path)
                self.assertEqual(download.call_count,1)
                build.assert_not_called()
                self.assertFalse(path.exists())

    def test_success_uses_cloud_resource_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'new.duckdb'
            with patch('cloud_bootstrap.download',return_value={'status':'downloaded'}) as download, patch('cloud_bootstrap.build_database') as build:
                ensure_database(tmp,path)
                self.assertEqual(download.call_count,5)
                build.assert_called_once_with(Path(tmp),path,memory_limit='256MB',threads=1)
