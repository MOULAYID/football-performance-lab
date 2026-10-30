# Streamlit Community Cloud deployment

Use these exact settings at https://share.streamlit.io:

- Repository: `MOULAYID/football-performance-lab`
- Branch: `setup/data-access-audit`
- Main file: `cloud_app.py`
- Advanced settings → Python: **3.12**
- Secrets: none required for the current public Kaggle download route.
- Suggested app subdomain: `football-performance-lab` (availability is not guaranteed).

Deploying the branch does not merge the PR. Subsequent pushes to this branch can update the hosted app. Use a separate release branch later if you need deployment isolation.

## First launch

`cloud_app.py` provisions the database, then runs the existing app. It downloads the five required CSVs from the publisher-linked Kaggle distribution, using the existing downloader and integrity checks. This involves several hundred MB and can take minutes. It stops on denied downloads without bypasses or retries. The build uses a 256 MB DuckDB memory limit and one thread, with temporary spill files. This memory limit is for DuckDB, not the entire Python/Streamlit process.

The database is reused while present. A fresh Cloud filesystem requires another download/build. Source URLs are not a pinned dataset version; later downloads can differ. File hashes and build provenance remain recorded in the database. No third-party CSV/database or credentials are committed to GitHub.

Initialization is serialized, and failure is cached to avoid visitor refreshes repeatedly triggering downloads. An owner should inspect logs, resolve the issue, then reboot the app to retry. Do not add secrets to code. Existing `.gitignore` excludes `.streamlit/secrets.toml` and local data.

Local launch remains `python -m streamlit run app.py`; to test the hosting entry point use `python -m streamlit run cloud_app.py`. Existing downloads/database are reused.

## Validation and limitations

45 offline tests passed. A fresh database build from cached real CSVs succeeded with 256 MB / one thread: 8,908 matches, 272,457 appearances and 5,526 players. The cloud entry point loaded the existing database in Streamlit AppTest. The cold-start UI path was checked with mocked provisioning, separately from the real build test. Community Cloud's network access, resource availability and deployed browser rendering still require live verification.

The app displays source attribution and coverage limitations. The dataset publisher's repository advertises CC0, but this project has not independently established all underlying data-use rights. Hosting through runtime downloads does not settle that question. No claim of permission clearance or independent full-data accuracy is made.

If deployment fails, check app logs for download denials, dependency errors or memory limits. Select Python 3.12 explicitly; the current chart stack was not tested on Python 3.14. Do not deploy `app.py` alone on a fresh instance: it expects a prebuilt database and will show local build instructions.

Official deployment guide: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
