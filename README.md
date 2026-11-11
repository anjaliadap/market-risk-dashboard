# Market & Risk Intelligence Platform

Python 3.12 / Streamlit research application, extended in place with saved Excel ingestion. The sponsor workbook is the primary source for 18 mapped sections (19 substantive worksheets), including 46 interactive charts and 8 tables. Existing independent FRED views and assumption tools remain available. Supply, Financing, and Workbook Administration are now navigable. See the [workbook audit](docs/excel_integration_map.md) and [local operations guide](docs/excel_operations.md) for source limitations and acceptance work still outstanding.

## Local setup (Windows PowerShell)

Install Python 3.12 and [uv](https://docs.astral.sh/uv/). From this repository:

```powershell
uv sync --frozen
uv run alembic upgrade head
uv run python -m scripts.import_workbook "C:/approved/local/master.xlsx"
uv run python -m scripts.refresh_market
uv run python -m scripts.refresh_macro
uv run streamlit run dashboard/app.py
```

On Linux the same uv commands work. No paid infrastructure required. Dependencies are pinned in `uv.lock`. Optional `.env` (copy `.env.example`) selects `DATABASE_URL`; defaults to `sqlite:///data/research.db`. Run all commands from the repository root. For PostgreSQL, install its SQLAlchemy driver and set its URL; PostgreSQL has not been integration-tested.

## Ingestion and checks

```sh
uv run python -m scripts.refresh_market --series DGS10 SP500 VIXCLS
uv run python -m scripts.refresh_macro
uv run python -m scripts.refresh_ai
uv run python -m scripts.import_historical_events config/historical_events.csv
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

`refresh_ai` currently reports that no verified AI provider exists; this is not a successful company-data ingestion. Jobs return nonzero on provider failure. FRED graph CSV does not require a key, but network access to `fred.stlouisfed.org` is required. Bloomberg is an optional interface only. SEC, EIA and other API credentials are not requested because those connectors are not implemented.

Do not place credentials in source control. Ingestion preserves stored values on failure, logs errors, and retains changed observations as retrieval vintages. A button initiates bounded background refresh; independent scheduled commands are recommended. Windows Task Scheduler can execute the ingestion commands from this working directory. Data errors appear in System Status; no observations appear until ingestion succeeds. HTTP 403 proxy errors require environment network settings, not fabricated API keys.

The supplied workbook and Word specification have been audited. The provider reads saved caches without changing the original workbook or recalculating Bloomberg/Excel formulas. Configure `EXCEL_WORKBOOK_PATH` in `.env` for automatic detection while the app is open; use `python -m scripts.import_workbook --watch` for a separate watcher. Use one watcher process. Set `DATABASE_URL` and `EXCEL_ARTIFACT_DIR` to a local, non-synchronized folder before importing licensed data; the current workstation's ignored `.env` does this. Source files, extracted images, and financial snapshots are not committed. No remote Bloomberg access, upload, deployment or paid infrastructure is provisioned.
