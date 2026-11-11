# Analyst guide

The saved sponsor workbook is primary on mapped pages. Workbook charts use saved Excel calculations; hover distinguishes forward estimates, and each chart names its source and latest historical observation. Tables retain Excel number formats and sponsor benchmarks. Missing caches remain unavailable. Use Workbook Administration to inspect import health and manual dependencies or request **Reimport Workbook**. Stable saved versions import in the background while the app is open; successful imports update the page automatically. Saving a file does not certify a Bloomberg refresh. See [local workbook operations](excel_operations.md) for the standalone watcher and range-extension limits.

Applicable pages offer **Show independent FRED observations for comparison**. The following controls apply to those independent views; they do not refresh Bloomberg or change Excel calculations.

Choose Market, Macro or AI sections in the grouped sidebar. Tables show available observations, units, observation dates, original retrieval timestamps and source links. Missing data is marked UNAVAILABLE. Charts support Plotly zoom, hover and export. Use chart start and series selection to inspect history; CSV downloads include source metadata.

Use the freshness button to enqueue eligible datasets, then rerun after completion. Scheduled ingestion is preferred for regular use. Inspect Data Sources & System Status for failures and last successful jobs. All observations are delayed; publication timestamps are unknown unless supplied. Do not interpret checklist inputs as predictions. Scenario controls and justified P/E are assumptions, not observed financial data.

Pages with unavailable feeds describe the dependency. Navigation availability does not establish analytical completion. No synthetic financial observations are supplied.

## Visual conventions

Market pages use navy accents, Macro pages use teal, and AI pages use plum. White cards and consistent chart layouts sit on a light background. Signed changes use muted green for positive numbers and muted red for negative numbers; these colors describe direction, not investment recommendations. Amber marks delayed, stale or unavailable data. Status text remains visible alongside color. CSV exports keep original values and source metadata.

Shared presentation utilities live in `dashboard/styles/theme.py`, layout rules in `dashboard/styles/institutional.css`, and native Streamlit light-theme defaults in `.streamlit/config.toml`. Theme helpers format display values without changing analytics, storage or exports.
