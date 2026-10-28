# Run the local player explorer

From the project folder in Git Bash:

```bash
git switch setup/data-access-audit
git pull --ff-only origin setup/data-access-audit
python -m pip install -r requirements.txt
python scripts/build_database.py --download
python -m streamlit run app.py
```

Open the local URL shown by Streamlit (normally http://localhost:8501). Stop with Ctrl+C. No JavaScript, backend server framework or API key is required. This command starts a local app; it does not publish a website.

Use league, season, name, minimum-minutes and snapshot-position filters. Select up to four players for totals, a metric chart and historical club stints. Comparisons stay within one league and season. Missing values remain unknown, and league coverage warnings appear above all tabs.

The app reads `data/processed/football.duckdb`. To use another database, set `FOOTBALL_DB_PATH`. Rebuilds invalidate the app cache using the file modification time; finish the build before refreshing the app.

[Database model](DATABASE.md) · [Independent sample checks](SAMPLE_VALIDATION.md)

Test with `python -m unittest discover -s tests -v`. Streamlit's AppTest exercises the app without a browser. The fixture tests cover filtering, player selection, missing database guidance and coverage warnings; they do not replace visual browser inspection.

## Python compatibility and isolated setup

Use Python 3.12 for this pinned stack. The earlier Python 3.10+ description was too broad: Altair 5.5 can fail on Python 3.14 with `_TypedDictMeta.__new__() got an unexpected keyword argument 'closed'` (https://github.com/vega/altair/issues/3874). Updating typing-extensions alone does not repair Altair choosing the standard-library TypedDict on that runtime.

Stop Streamlit. In Git Bash, check `python --version` and `py -0p`. If necessary, install Python 3.12 from python.org. Create a separate environment without deleting the existing one:

```bash
deactivate
py -3.12 -m venv .venv312
source .venv312/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
python -c "import altair; print(altair.__version__)"
python -m streamlit run app.py
```

Skip `deactivate` if no environment is active. This preserves downloaded data and the database. In future terminals use `source .venv312/Scripts/activate`. Verified locally: Python 3.12.14, Altair 5.5.0 and typing-extensions 4.16.0 import and serialize a bar chart successfully. Windows execution remains to be confirmed on the user's machine.
