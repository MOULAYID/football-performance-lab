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
