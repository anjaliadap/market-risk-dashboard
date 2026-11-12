# Market & Risk Intelligence Platform

Python 3.12 / Streamlit research application with saved Excel ingestion and independent public-data providers. The sponsor workbook mapping covers 18 sections (19 substantive worksheets), including 46 interactive charts and 8 tables. Margin Debt, Bull vs Bear, and BTC open with public-source calculations by default; their source selector also offers the imported workbook's saved view when a validated import exists. Other mapped sections retain the existing workbook-first behavior. Independent FRED comparisons and analyst assumption tools remain available.

The three public views include validated calculations, source dates, refresh status and CSV exports. The market-cap comparison uses a labeled Federal Reserve proxy, and AAII forward-return comparisons use price returns rather than Bloomberg total returns. Start with [INTEGRATION.md](INTEGRATION.md) for setup and methodology. See the [workbook audit](docs/excel_integration_map.md), [source coverage](docs/data_coverage.md) and [local workbook operations guide](docs/excel_operations.md) for saved-workbook behavior and remaining dependencies. Supply, Financing and Workbook Administration remain navigable.

## Local setup (Windows PowerShell)

Install Python 3.12 and [uv](https://docs.astral.sh/uv/). From this repository:

```powershell
uv sync --frozen
uv run alembic upgrade head
uv run python -m scripts.refresh_workbook_sections
uv run streamlit run dashboard/app.py
```

On Linux the same uv commands work. No paid infrastructure is required. Dependencies are pinned in `uv.lock`. Optional `.env` (copy `.env.example`) selects `DATABASE_URL`; the default is `sqlite:///data/research.db`. Run all commands from the repository root. For PostgreSQL, install its SQLAlchemy driver and set its URL; PostgreSQL has not been integration-tested.

To enable the sponsor workbook's saved views, import an approved local file:

```powershell
uv run python -m scripts.import_workbook "C:/approved/local/master.xlsx"
```

The public providers for the three sections require outbound HTTPS, with no Bloomberg terminal, user login, paid feed or user-provided API key. Source availability and publisher terms still apply. Their live endpoint checks were performed on **October 22, 2026**; that historical verification does not establish current endpoint availability or current observation freshness.

## Ingestion and checks

```sh
uv run python -m scripts.refresh_market --series DGS10 SP500 VIXCLS
uv run python -m scripts.refresh_macro
uv run python -m scripts.refresh_ai
uv run python -m scripts.refresh_workbook_sections --due-only
uv run python -m scripts.export_workbook_sections --output-dir data/workbook_sections
uv run python -m scripts.import_historical_events config/historical_events.csv
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

`refresh_ai` currently reports that no verified AI provider exists; this is not a successful company-data ingestion. Jobs return nonzero on provider failure. FRED graph CSV does not require a key, but network access to `fred.stlouisfed.org` is required. Bloomberg is an optional interface only. SEC, EIA and other API credentials are not requested because those connectors are not implemented.

Do not place credentials in source control. Public ingestion preserves stored values on failure, logs errors and retains changed observations as retrieval vintages. Related AAII and Strategy fields are validated and saved together. While a public section is open, its view rechecks every minute; quote requests are limited to once every five minutes, other inputs to daily checks, and failed requests to one retry per hour. These retrieval schedules do not remove publication lag. A closed app does not run its background worker. Windows Task Scheduler or another existing scheduler can execute the documented refresh command from this working directory; no recurring job is installed by the code. Export commands use saved observations, so stop an unattended refresh/export sequence if refresh returns nonzero.

Data errors appear in System Status and each public section's source-status panel. No observations appear until ingestion succeeds. Network or access errors are reported without substituting old hardcoded workbook values. Strategy uses the website's published read-only content-delivery configuration; changes to that public configuration may require the documented provider maintenance or environment overrides.

The supplied workbook and Word specification have been audited. Excel ingestion reads saved caches without changing the original workbook or recalculating Bloomberg/Excel formulas. Configure `EXCEL_WORKBOOK_PATH` in `.env` for automatic save detection while the app is open; use `python -m scripts.import_workbook --watch` for a separate watcher. Use one watcher process. Set `DATABASE_URL` and `EXCEL_ARTIFACT_DIR` to a local, non-synchronized folder before importing licensed data. Source files, extracted images and financial snapshots are not committed. Selecting an imported workbook view does not merge it with independent public observations. No remote Bloomberg access, upload, deployment or paid infrastructure is provisioned.
