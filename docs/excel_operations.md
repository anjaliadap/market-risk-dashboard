# Saved workbook operations

The audit and machine-readable mapping were produced before implementation. See [excel_integration_map.md](excel_integration_map.md) for every sheet, chart range, formula column and manual dependency. The Word document supplies the requested presentation. Its embedded pictures are local reference material, not app assets or instructions to execute.

## Local configuration

Use a company-approved local master or synchronized source workbook. The developer workstation is configured through ignored `.env` to read the supplied Downloads workbook and store snapshots in `C:/Users/adapa/AppData/Local/MarketRiskDashboard/research.db`. The previous `data/research.db` is preserved. Audit inventory and extracted reference images also live under local AppData, outside the OneDrive project. No licensed source values are in the versioned mapping.

For another workstation, create a local folder outside file synchronization, then set:

```dotenv
DATABASE_URL=sqlite:///C:/approved/local/market-risk/research.db
EXCEL_WORKBOOK_PATH=C:/approved/source/master.xlsx
EXCEL_ARTIFACT_DIR=C:/approved/local/market-risk
EXCEL_SETTLE_SECONDS=5
EXCEL_POLL_SECONDS=10
```

The database's parent folder must exist. Credentials are not needed for local saved-value ingestion. Environment variables override `.env`. Bloomberg must be refreshed in the company's authorized Excel environment, recalculated, and saved. Python does not connect to a Terminal or run Excel.

```powershell
uv run alembic upgrade head
uv run python -m scripts.import_workbook
uv run python -m scripts.compare_excel
uv run streamlit run dashboard/app.py
```

The app polls every 10 seconds while a session is open. It waits for stable size/mtime observations over the settling interval, then hashes bytes. A single background worker validates a consistent bytes snapshot, checks required sheets, header anchors, metric types/number formats, dates, duplicates and prior-value continuity. It rechecks the file hash before publication. One short database transaction publishes the whole validated snapshot; unsuccessful imports only add a failure log. Previously valid points cannot silently become missing. Existing initial gaps and error text are retained as unavailable with diagnostics. File modification time, formula TODAY() and successful import are not Bloomberg refresh evidence.

In Workbook Administration, review the current path/modification time, last successful import, latest validated historical date (excluding estimates), numeric metric count, errors, missing caches, manual notes and coverage. **Reimport Workbook** requests another validation even for identical bytes and still waits for writes to settle. A successful automatic import triggers a full app rerun so charts update without manually refreshing the browser. Closed browser sessions do not run a watcher.

For continuous detection without a browser:

```powershell
uv run python -m scripts.import_workbook --watch
```

Use a single watcher; the worker is process-local, not a distributed lease. Windows Task Scheduler may instead run the one-shot command from the repository root. This implementation does not configure a scheduled task or start a permanent service. Immutable full snapshots consume storage; set an approved retention policy before long-term operation. Failed versions are not retried continuously until bytes/mapping change or an operator requests reimport.

## Layout and calculation maintenance

`config/excel_mapping.json` contains all Excel coordinates. Streamlit reads named database snapshots, not worksheets. Date axes on combo charts use each series' own date range. Prices, yields, percent fractions, futures and source-specific quantities retain sponsor semantics and Excel number formats. Unexpected format changes fail validation. General/decimal variations already present in the audited workbook are explicitly allowed. Types and bounds can be strengthened per metric in the mapping; no cross-unit conversions are guessed.

Chart endpoints are fixed to match the sponsor's saved charts. Some source columns extend beyond those endpoints; these charts will remain clipped until the mapping is reviewed and extended. Extending a Bloomberg spill alone does not extend the central mapping or fixed Excel calculation ranges. New observations inside configured ranges import automatically. S&P Relative rolling formulas, Gold to Oil row-463 endpoints, FINRA inputs, Strategy inputs and checklist statuses need operator maintenance described in the audit. This is a known limit on unattended coverage, not a freshness guarantee.

Mappings mark sparse company-chart bars as last-reported-quarter markers; blank marker cells are intentional. Forward estimates appear in hover metadata and are excluded from latest historical dates. Checklist saved flags govern red readings; red-font manual inputs retain their original presentation. Scores are saved sponsor outputs, not Python recession probabilities. New missing formula caches remain unavailable; valid older snapshots stay active on regression.

After an intentional layout or historical-range change, audit it, review the mapping diff and resolve continuity rejections explicitly. There is no UI button to bypass validation. Restore a corrected compatible workbook or use a separately approved new database for a materially different contract. Do not delete old snapshots to conceal a data regression.

Reproduce the audit and compare calculations:

```powershell
uv run python -m scripts.audit_workbook "C:/approved/source/master.xlsx"
uv run python -m scripts.map_workbook
uv run python -m scripts.compare_excel "C:/approved/source/master.xlsx"
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

The generated local inventory contains sensitive cached values and formulas. Keep it outside synchronized/public folders. The mapping generator uses only labels, source references, formatting and structural counts. Comparison reports contain pass/mismatch/unavailable statuses, not copied financial data. The initial 11 checks matched BTC valuation/coverage, Gold to Oil implied prices, reciprocal-yield P/Es and saved checklist fractions. These checks validate arithmetic; they do not certify Bloomberg freshness or manual assumptions. Existing FRED ingestion remains separate. SEC, Treasury and EIA connectors were not implemented in the original application and are still external-source work.

## Later OneDrive / SharePoint integration

The local provider is independent of file transport. A later company-managed reader can discover changed drive items with Microsoft Graph [driveItem delta](https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0), retain the returned delta token, and obtain the file using the [driveItem content endpoint](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0). Follow pagination and handle expired tokens/resynchronization. Do not treat eTag or lastModifiedDateTime as Bloomberg refresh evidence.

Use a tenant-approved Entra application, least-privilege read access approved by the company, and credentials stored outside source control. Download to a local staging file, finish and verify the download, atomically promote it to the watched source path, then run the same validation. No write-back/upload is needed. Confirm Bloomberg-derived-data licensing and distribution rights before enabling any company upload, hosting or wider access. No Graph credentials, integration or paid service is required or enabled for local development.
