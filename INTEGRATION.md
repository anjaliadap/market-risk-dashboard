# Margin Debt, Bull vs Bear and BTC integration

This update extends the Python 3.12 / Streamlit project at
https://github.com/anjaliadap/market-risk-dashboard, based on commit
`8cde9c457357da1fa61d62be811ac46cb8282cd8` (main as of November 12, 2026).
It implements the three requested workbook tabs and their corresponding Word
Appearance examples. Other ideas in the employer's email are outside this update.

## Install and run

From this repository branch or an extracted source ZIP, install Python 3.12 and uv, then
run the following from the project root:

```sh
uv sync --frozen
uv run alembic upgrade head
uv run python -m scripts.refresh_workbook_sections
uv run streamlit run dashboard/app.py
```

Open Market → Margin Debt, Bull vs Bear, or BTC. These pages default to public data;
the Data source selector also preserves access to the imported workbook snapshot.
The first refresh requires outbound HTTPS.
No Bloomberg terminal, user login, paid feed or user-provided API key is required for these
providers. Public endpoint availability and publisher terms still apply. Data downloads are
made at runtime; the distribution contains code and tests, not the user's source documents
or a republished historical market-data database.

## What each section contains

| Section | Public inputs | Output |
|---|---|---|
| Margin Debt | FINRA monthly debit balances; FRED nominal GDP; Federal Reserve domestic public equity value | Sponsor historical reference table, margin/GDP and margin/public-equity-value charts, full-history means |
| Bull vs Bear | AAII complete public sentiment workbook and its weekly S&P 500 close column | Bull-minus-bear chart, latest reference line, current percentile/decile, mean forward-return table with highlighted current decile, counts and positive-return frequencies |
| BTC | Strategy public website datasets for holdings, debt, preferred notional and aggregate average acquisition cost; Coinbase BTC-USD ticker | The workbook's Strategy BTC holdings coverage table, 1:1 coverage price, downside and unrealized gain/loss |

### Margin Debt methodology

[FINRA](https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics)
reports customer debit balances in USD millions, usually in the third week following the
reference month. Dates are normalized by month, accommodating last-business-day workbook dates.

[GDP](https://fred.stlouisfed.org/series/GDP) is nominal USD billions at a seasonally adjusted
annual rate. Divide debt in millions by 1,000 before dividing by GDP. FRED labels quarters at
quarter start; charts use that quarter's end date and the exact matching FINRA month. This is
a descriptive stock-to-annualized-flow ratio, using currently revised data. It is not a
publication-aware historical backtest.

**Explicit alternative:** [Federal Reserve public corporate equities](https://fred.stlouisfed.org/series/BOGZ1LM883164115Q)
are quarterly market-value levels in USD millions. This replaces the workbook's monthly
Wilshire 5000 capitalization. The population and frequency differ. The denominator is a
dollar capitalization measure; index points are never treated as dollars. Both charts stop
at their latest matched quarter; no denominator or missing month is carried forward.
GDP history starts in 2000 and the equity comparison in 1997, matching the reference scope
where public inputs permit. The mean is the arithmetic mean of available matched ratios.

The historical 2000/2007/2018/2021 peaks and troughs reproduce the sponsor's rounded reference
figures. They remain reference assumptions, with Current calculated from the latest FINRA
month. Average and median comparisons use the 2007/2018/2021 rows. No new cycle is inferred.

### Bull vs Bear methodology

[AAII's public complete-history XLS](https://www.aaii.com/files/surveys/sentiment.xls)
supplies full Reported Dates, bullish/neutral/bearish fractions and weekly S&P 500 closes.
Sentiment fractions are multiplied by 100 once; spread is bulls minus bears in percentage
points. Dates come from the XLS, rather than guessing years from the recent HTML table.
The XLS reported-date label may differ from the website's survey week-ending label.

Percentiles match Excel PERCENTRANK.INC at existing observations, including first tied ranks,
three-decimal truncation and half-up rounding to an integer percentile. Percentiles 0–10
map to decile 1, 11–20 to decile 2, through 91–100 to decile 10. Source precision is retained.
Full-sample descriptive deciles and their historical membership can change on refresh.

**Explicit alternative:** forward returns use AAII-reported weekly S&P 500 **price** closes,
excluding dividends, rather than Bloomberg S&P 500 total returns. The precise underlying
close timestamp is not supplied. Start and horizon endpoints use the first available reported
weekly close on/after the survey date and each 1/3/6/12-calendar-month target, within seven
days. This weekly resolution can differ from daily calendar-date returns. Incomplete future
horizons remain blank. Tables expose separate valid counts per horizon and positive-return
frequencies. Weekly observations overlap, so observations are not independent. These are
descriptive statistics, without a predictive/tradable strategy claim.

### BTC methodology

[Strategy](https://www.strategy.com/) publishes its holdings, outstanding debt/preferred
notional and ledger average acquisition cost. These are gathered as one coherent company
snapshot; source dates and retrieval dates remain distinct. Debt/preferred amounts are USD
notional, not securities market capitalization. The average cost is for the aggregate BTC
position, not the latest purchase's transaction price. Holdings reconcile across the company
datasets before a snapshot is saved.

The provider uses the website's publicly shipped, read-only Contentstack delivery
identifiers. They grant no write access and require no user account. If Strategy
rotates its public configuration, maintain the provider defaults or set the optional
`STRATEGY_PUBLIC_CONTENT_API_KEY` and `STRATEGY_PUBLIC_CONTENT_DELIVERY_TOKEN`
environment overrides to the website's new public delivery values. Access/schema failures
retain the prior complete snapshot and produce a visible refresh error.

[Coinbase's public BTC-USD ticker](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-ticker)
provides the last-trade spot price with its actual UTC source timestamp. The optional
COINBASE_BTC_USD history provider supports completed UTC daily candles; open current-day
candles are excluded and genuine gaps remain missing. Coinbase exchange prices differ
from the workbook's Bloomberg currency reference.

The table reproduces the workbook:

- BTC value = BTC held × spot / 1,000,000, in USD millions.
- Claims = total debt + preferred notional, displayed in USD millions.
- LTV = claims / BTC value; coverage = BTC value / claims.
- 1:1 coverage price = claims in USD / BTC held.
- Downside = 1:1 price / current spot − 1.
- Gain/loss = (spot − average cost per BTC) × BTC held / 1,000,000.

Positive denominators and reciprocal/amount reconciliations are enforced. Company data and
quote times can differ and are shown separately. This simplified coverage calculation
excludes cash, other assets, taxes and security conversion terms; it is not a default estimate.
Current holdings are never backcast into a historical portfolio.

## Automatic updates and file integration

While a section is open, its view rerenders every 60 seconds. Source requests are throttled
to five minutes for the BTC spot quote and daily for other inputs, with a one-hour retry
cooldown after failure. It refreshes as the publishers release data; monthly and quarterly
inputs are not real-time observations. A closed app does not run its background worker.

For unattended refresh, run this command from the project root using Windows Task Scheduler,
cron, or your existing host scheduler (for example every five minutes):

```sh
uv run python -m scripts.refresh_workbook_sections --due-only
```

This code includes no installed recurring job or hosting service. It can run inside the
existing deployment. SQLite and ResearchRecord source metadata need persistent storage.
The existing schema supports the public-source fields; run the repository's existing
Alembic migrations, including the saved-workbook import migration, before starting the app.

For file-based integrations, export the saved calculations after a successful refresh:

```sh
uv run python -m scripts.refresh_workbook_sections
uv run python -m scripts.export_workbook_sections --output-dir data/workbook_sections
```

Stop the sequence if the refresh returns nonzero. The exporter publishes `manifest.json`
pointing to an immutable snapshot containing `margin_debt.csv`, `bull_vs_bear.csv`, `btc.csv`
and supporting ratio/decile/reference files. Consumers should read the manifest and then its
listed files to avoid mixing generations. Source dates, units, retrieval details and SHA256
checksums travel with the batch. Source files and units are also available in the dashboard's
CSV downloads and source-status panel.

## Validation and operations

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Tests cover endpoint schema changes, units, duplicate/future dates, source failures,
percentage totals, Excel percentile ties/rounding, calendar horizons, maturity, missing
periods, expanding history, transactional rollback, stale quotes and populated views.
Related AAII and Strategy inputs are validated before one database transaction. If any
required field fails, the entire group remains unchanged and all group members record a
failed job. Changed source observations retain local retrieval vintages; these are not
historical publication vintages. Tests use isolated synthetic fixtures only.

The source-status panel reports missing data, stale observation/quote ages, latest retrievals
and refresh failures. A fresh retrieval does not imply a newly published observation. Prior
valid data remain visible on failure with a warning. Schema changes or unavailable endpoints
produce errors; the code never falls back to old hardcoded workbook values. Runtime network
failures return a nonzero command exit status. See [verification notes](docs/workbook_verification.md).
