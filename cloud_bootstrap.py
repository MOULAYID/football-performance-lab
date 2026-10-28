"""Prepare the hosted database without committing third-party data to Git."""
from pathlib import Path
from threading import Lock
from scripts.build_database import FILES, build_database
from scripts.audit_public_data import download, KAGGLE_BASE

_BUILD_LOCK = Lock()


def ensure_database(data_dir, output):
    data_dir, output = Path(data_dir), Path(output)
    with _BUILD_LOCK:
        if output.is_file():
            return output
        for name in FILES:
            result = download(KAGGLE_BASE + name + '.csv', data_dir / (name + '.csv'))
            if result['status'] not in ('cached', 'downloaded'):
                raise RuntimeError(f'Dataset download unavailable for {name}: {result["status"]}. No database was published.')
        build_database(data_dir, output, memory_limit='256MB', threads=1)
        return output
