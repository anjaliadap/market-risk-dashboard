# Saved-workbook Market and Empirical pages

Gold to Oil, NDR, Intra-Sector Spread and Trend Following use the updated sponsor
workbook and Process document. These pages do not request public market data or
substitute proprietary readings. Earlier workbook mappings remain available for
their original layout, in a separate import profile.

## Run with the updated workbook

From this branch, install the pinned dependencies and migrate the local database:

```sh
uv sync --frozen
uv run alembic upgrade head
```

Set the path in a local, ignored `.env` file. Use the latest workbook supplied for
this project. The workbook, extracted data, database and personal paths are not
part of the published source code.

```dotenv
PROCESS_WORKBOOK_PATH=C:/approved/source/latest-master.xlsx
```

An explicit `PROCESS_WORKBOOK_PATH` takes precedence over `EXCEL_WORKBOOK_PATH`.
The fallback exists for installations with one master workbook. The app does not
choose a source by filename or modification time, and does not combine old and
new workbooks. The configured file is authoritative for these four pages.

```sh
uv run python -m scripts.import_process_workbook
uv run streamlit run dashboard/app.py
```

Alternatively pass the workbook path to the one-shot import command. Set the
environment path as well to enable subsequent save detection in the app.

Open **Empirical → Intra-Sector Spread / Trend Following** or **Market → Gold to
Oil / NDR**. The local routes are `/intra-sector-spread`, `/trend-following`,
`/gold-to-oil` and `/ndr`. No network ingestion command is needed for these pages.
The existing public Margin Debt, Bull vs Bear and BTC pages remain independent.

## Data and calculations

| Page | Source | Calculation and presentation |
| --- | --- | --- |
| Gold to Oil | Saved `Gold to Oil` worksheet, Bloomberg `XAUUSD Curncy` and `CO1 Comdty` prices | Gold/Brent ratio and long-term mean, Brent futures on a separate dollar axis, same-date implied gold/Brent prices and percentage changes |
| Intra-Sector Spread | Saved `Intra-Sector Spreads` worksheet | Thirteen supplied sector percentiles versus their saved average reference, with 1/3/6/12-month changes in percentile points |
| Trend Following | Saved `Trend-Following` worksheet | Full monthly quintile history, discrete filled step chart, latest reading and 1/3/6/12-month changes in quintile points |
| NDR | Saved `NDR` worksheet | Grouped model readings, historical returns/start years, prior/current warning shares, strict source thresholds, and the record-highs scenario calculator |

Gold is USD per troy ounce. `CO1` is Brent front-month **futures**, USD per barrel;
the workbook's “Oil Spot” wording is not repeated as a spot-market claim. Gold
and Brent dates must match. The averaging population follows the saved
`AVERAGE(K...)` formula, including the Current row when inside that range. A
missing required price makes the affected ratio and mean unavailable; it does
not shorten the averaging population silently.

The uploaded Gold display panel contains conflicting saved values and a
formula/cache contradiction. The dashboard calculates ratio = gold / Brent,
implied gold = mean ratio × Brent, implied Brent = gold / mean ratio, and
change = implied / current − 1 from the workbook's same-date source inputs.
It compares these with the saved calculation/summary cells and exposes the
conflicts under Workbook source and checks. It does not modify the workbook.

Intra-sector and Trend readings are preserved, not regenerated as models.
Hidden dated source columns are included. Missing readings remain null, and
changes require the exact calendar baseline month. An internal missing or
duplicate date header rejects the candidate file instead of silently shortening
its history. New contiguous monthly columns are detected before the summary
block. Gold source rows are discovered through the saved Current marker, so a
new monthly row does not require changing an old fixed chart endpoint. Source
formula bounds still govern the mean; changing a worksheet's structure or
definitions requires reviewing `config/process_sections.json`.

NDR keeps the supplied text, source model codes and notes. The next-year median
gain is distinguished from annualized returns. Its three warning rules are
strictly greater than the supplied 50%, 40% and 50% thresholds. The internal AAII
row has a blank reading and a saved external-workbook return link; the dashboard
preserves those facts instead of replacing them with its public AAII series.
Record-highs scenario labels and assumptions remain those saved in the workbook.

## Monthly update workflow

1. Update NDR, Intra-Sector Spreads and Trend Following manually in the master
   workbook, as directed by the Process document.
2. Add the Gold monthly row, refresh Bloomberg formulas in Excel, recalculate,
   and save. Keep the Current marker and helper/formula ranges correct.
3. Leave the configured file accessible. While one of these pages is open, the
   app checks every ten seconds, waits for file writes to settle, validates one
   immutable byte snapshot and publishes all four sections in one transaction.
4. Review source checks. A failed/partial save retains the previous valid Process
   snapshot and displays the failed import. Previously valid historical inputs
   cannot silently disappear from a later import.

The snapshot records file/mapping SHA-256, import time, source reference dates,
and cell-level diagnostics. Import time and `TODAY()` do not certify Bloomberg
freshness. NDR's manual model table has no report date; its calculator date is
shown separately and is not assigned to those manual readings.

For detection without an open dashboard, run one watcher process:

```sh
uv run python -m scripts.import_process_workbook --watch
```

No watcher, external scheduler or Bloomberg connection is installed automatically.
Run migrations before opening an existing database. Migration `0003` assigns
older imports to the `legacy` profile without replacing them. Process imports,
failure records and polling state are separate, so unrelated old-layout pages
and public-source observations are not overwritten by a Process import.

## Verification

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Tests use synthetic workbooks and isolated databases. They cover same-date
prices, correct mean population, inconsistent caches, calendar changes, dynamic
monthly extensions, missing/invalid values, exact threshold boundaries, source
profile separation, migration/backfill, failed-save retention and populated page
rendering. Local verification against the supplied updated workbook is separate
from those fixtures; source documents and numerical snapshots are excluded from
GitHub.
