# Market & Risk Intelligence Platform

Python 3.12 / Streamlit research application. **Initial implementation; not sponsor-demo ready.** All 18 sections plus Executive Overview and System Status are navigable. Many requested data products are explicitly unavailable. See [implementation tracker](docs/progress.md).

## Local setup (Windows PowerShell)

Install Python 3.12 and [uv](https://docs.astral.sh/uv/). From this repository:

```powershell
uv sync --frozen
uv run alembic upgrade head
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

The referenced Excel snapshot was not attached; its visual layout and moving-average labels could not be verified. No deployment or commercial services were provisioned.
