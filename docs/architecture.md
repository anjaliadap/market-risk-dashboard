# Architecture

`dashboard/app.py` uses Streamlit supported grouped Page/navigation APIs. `src/analytics/core.py` contains pure reusable calculations. `config/series.json` is the source registry. `src/providers/fred.py` handles keyless official FRED CSV retrieval and parsing. `src/database/store.py` stores revision rows and ingestion jobs via SQLAlchemy. Alembic initializes the schema. `src/refresh.py` has a single bounded worker, deduplication within one app process, daily retrieval checks and hourly failure cooldown. `scripts` jobs run independently.

SQLite writes are short transactions with a 30-second busy timeout. No external calls occur inside write transactions. Concurrent scheduled jobs are not globally deduplicated: use one scheduler process. A future durable worker needs cross-process leases, bounded queues, release-calendar policies and observability.

Research definitions/events/assumptions can use versioned research_records; instruments, calculation versions and normalized source/policy tables remain future work. Changed observation values append rows; unchanged values do not create duplicates. Latest successful retrieval is tracked in jobs, distinct from first retrieval time of an unchanged value. Deletions/retractions are not yet modeled. SQLite timestamps are normalized to UTC at interpretation boundaries; SQLite may return naive UTC values.

PostgreSQL URL support is architectural, not yet verified against a running PostgreSQL database. No authentication is provided. The original master specification is not fully implemented.

## Saved Excel source layer

Saved sponsor Excel is primary for mapped sections. src/providers/excel.py validates consistent bytes against config/excel_mapping.json, reading values and formulas separately without evaluation or writes. src/excel_sync.py detects stable saves and publishes immutable WorkbookImport snapshots through SQLAlchemy only after validation. Failure logs have no snapshot and never replace the last success. Provenance includes addresses, units/formats and formula metadata. Excel values do not share independent FRED observation IDs.

dashboard/excel_views.py contains reusable table/chart rendering. Existing pages dispatch mapped sections here and retain optional FRED comparisons and assumption tools. A fragment polls while the browser is open and reruns after publication; the CLI watcher supports operation without a browser. Use one watcher process. The ignored workstation configuration keeps snapshots and audit artifacts in local AppData outside OneDrive. See excel_operations.md for setup and the later Graph transport boundary.
