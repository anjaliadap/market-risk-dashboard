# Methodology and limitations

Returns are percentages from last available baseline at/before a calendar target, bounded by a date-gap tolerance. YTD uses prior year-end. Charts use observation dates; these are not release dates. Rates use 100 basis points per percentage point. VIX changes use index points. Equity histories are price indices excluding dividends. WTI, Brent and Henry Hub are spot, not futures; no roll methodology is claimed. Moving-average distance means price/MA minus one; constituent breadth is unavailable. Historical 252-session range is an approximation to 52 calendar weeks.

Percentiles use empirical less-than-or-equal ranks; deciles run 1–10. Volatility uses sample standard deviation of simple returns and 252 annual sessions. Ratios align exact common observations and reject zero denominators. Justified P/E assumes perpetual growth and payout = 1 − retention; invalid growth/discount denominators are rejected. Scenarios are deterministic compound-growth assumptions, not fitted forecasts.

Forward-return helper selects first observed session on/after the calendar horizon, with bounded tolerance. Its summaries are descriptive only: no publication-aligned sentiment backtest, nonoverlapping sample selector, confidence intervals or inference has yet been implemented. Do not use currently revised macro values as evidence of historical predictive performance. Retrieval vintages are not ALFRED publication vintages. Missing values are never silently forward-filled.

Release calendars, publication timing, holiday-aware staleness, historical peak/recession UI comparisons and statistical forecasting remain pending. Daily retrieval success is not proof a source has published the expected release.
