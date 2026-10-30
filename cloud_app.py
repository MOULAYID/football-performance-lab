"""Streamlit Community Cloud entry point. Local usage remains app.py."""
import logging
import os
from pathlib import Path
import runpy
import streamlit as st
from cloud_bootstrap import ensure_database

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('FOOTBALL_DB_PATH', ROOT / 'data/processed/football.duckdb'))


@st.cache_resource(show_spinner=False)
def prepare(path):
    try:
        ensure_database(ROOT / 'data/raw/public_audit/transfermarkt-kaggle', path)
        return True
    except Exception:
        # Cache failure too: visitor refreshes must not repeatedly trigger downloads.
        logging.exception('Hosted database initialization failed')
        return False


if not DB.is_file():
    with st.spinner('Preparing football data for the first launch. This may take several minutes…'):
        ready = prepare(str(DB))
    if not ready:
        st.error('The dataset could not be prepared. The app owner should check the Streamlit logs and reboot after resolving the issue.')
        st.stop()

runpy.run_path(str(ROOT / 'app.py'), run_name='__main__')
