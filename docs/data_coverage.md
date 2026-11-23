# Source coverage

Margin Debt, Bull vs Bear and BTC use public-source calculations by default. Each offers the imported workbook's saved view through its source selector when a validated snapshot exists. Other mapped sections retain the existing workbook-first behavior. Public observations and Excel snapshots remain separate; switching a view does not merge their metric identities or dates.

All 19 substantive worksheets were audited. The 2026-11 legacy mapping covers 62 charts and 10 tables across 21 sections. See the [full source/range audit](excel_integration_map.md). Dates and source metadata accompany charts. Import time does not attest Bloomberg freshness, and a source retrieval time does not establish a new observation or release date.

**Public endpoint verification: October 22, 2026.** The scoped checks retrieved valid FINRA, AAII, Coinbase, GDP/Fed equity-value FRED and Strategy public website data. This is a historical verification date, not a claim that those endpoints or saved observations are current today. Other original sections' independent feeds were not re-audited in this scoped update. See [integration methodology](../INTEGRATION.md) and [verification notes](workbook_verification.md).

| Section | Default or existing coverage | Saved-workbook coverage / remaining dependency |
|---|---|---|
| Momentum | Momentum & Controversy Scores (1955–), average, 70 threshold; trailing-change table | Dedicated page: signal board, episodes, S&P 500 returns after crossings. Manual monthly sponsor data; no public equivalent |
| FC Data | 14 failure-model share charts (11 sectors, 3 styles) with recession bars | Dedicated page: comparison, heatmap, statistics recomputed and checked against the saved summary. Manual monthly sponsor data |
| Failure Candidates | Sector/style summary with OPP/Patient weights, relative weights and risk flags | Dedicated page: rules re-applied as a check, exposure in 'Risk' sectors, positioning chart. Weights are manual inputs |
| Market Data | Equity/sector/rates/volatility/commodity snapshot; four breadth/flow charts | Authorized refresh, fixed chart endpoint review; Excel heatmap parity remains a visual refinement |
| Bear Market | Saved current/benchmark checklist, flags and score | Historical averages preserved; operator-dependent flags must be reviewed |
| S&P vs Bonds | Two cached spread/relative-multiple charts | Authorized refresh; sponsor calculation definitions retained |
| Valuation | Historical benchmarks and current saved values | Dedicated page: rate-relative earnings yield, equity value/GDP, profits/GDP, P/E models (see sections.md) |
| S&P 500 Fundamentals | Four charts, including payouts and growth | Two BQL anchor caches absent; early Y/Y values unavailable |
| Margin Debt | Public FINRA monthly debit balances, historical references, quarterly GDP ratio and labeled Fed public-equity-value ratio | Optional saved benchmarks and two sponsor ratio charts remain available. Public quarterly equity value differs from monthly Wilshire 5000 capitalization; workbook FINRA and hardcoded market-cap inputs still require authorized maintenance. |
| S&P Relative | Gold/WTI ratios, 7-year averages, current lines and underlying prices (2026-11 layout) | Dedicated page: distance from average, percentiles, implied levels, FRED S&P 500 ÷ WTI spot cross-check; no free gold history. Manual formula extensions |
| Gold to Oil | Saved Process workbook ratios, historical averages and implied prices | Requires a validated Process workbook snapshot |
| NDR | Saved warning probabilities and signal thresholds | Requires a validated Process workbook snapshot |
| Intra-Sector Spread | Saved sector dispersion and spread history | Requires a validated Process workbook snapshot |
| Trend Following | Saved trend-following signals and comparisons | Requires a validated Process workbook snapshot |
| Banks | Net charge-offs chart | Dedicated page: Fed delinquency/charge-offs by loan type, SLOOS, H.8 loans/deposits; FDIC QBP not connected |
| Bull vs Bear | Public AAII history, bull-minus-bear chart, Excel-compatible percentiles/deciles, completed forward price-return comparisons, counts and positive-return frequencies | Optional saved spread chart, decile table and auxiliary AAII chart remain available. The audited workbook contains 2,025 BQL forward-return error texts. Public returns use weekly price closes, exclude dividends and differ from Bloomberg total returns; comparisons are descriptive and overlapping. |
| VIX & Options | Three charts and reference lines; options-activity percentiles | Fixed chart endpoints clip longer source histories. Dedicated page: VIX, VIX3M, VXN, OVX, GVZ, term structure, implied − realized, signal board |
| BTC | Strategy public holdings, debt/preferred notional and portfolio average acquisition cost, combined with a timestamped Coinbase quote for the coverage table | Optional sponsor saved coverage table remains available. Company fields reconcile as one snapshot, with component dates distinct from quote time. Public delivery configuration changes may require provider maintenance; the imported workbook's company inputs remain manual. |
| Housing | Six charts with series-specific dates and secondary axes | Dedicated page: PMMS, pipeline, new-home sales/supply, payment affordability; NAR existing-home data workbook-only |
| Energy | Five production/rig/efficiency charts | Futures vs spot and gas units preserved; EIA balances not connected |
| Recession | Saved 17-indicator checklist and Sahm chart | Dedicated page: automated 17-item checklist (15 from FRED; LEI/PMI use saved flags), checklist at prior recession starts; no real-time vintages |
| Consumer | Three charts | Dedicated page: real income/spending, real wages, debt service, credit growth, card stress, sentiment |
| Demand | Six company charts with reported/forward separation | Dedicated page: automated Demand Tracker; BLS productivity and Fed/Census semiconductor proxies; SIA billings via analyst log |
| Financing | Four sponsor charts | Dedicated page: automated Financing Tracker; funding gap from saved data; FRED credit spreads, NFCI, SLOOS, corporate debt/GDP |
| Supply | No workbook source | Dedicated page: FRED bottleneck proxies (backlogs, grid-equipment PPI, utilization); GPU pricing, capacity, vacancy and lead times via sourced analyst logs |
| Forecasting | Existing analyst assumption tool | Hidden from navigation (sponsors do not need it). Code kept; re-enable by adding it back to `config/pages.json` |

Overview summarizes workbook coverage when a valid snapshot exists. Workbook Administration shows import health, missing values and manual dependencies, including the three sections whose default views use public sources. Data Sources & System Status exposes the independent-source registry and ingestion jobs. The three public sections also show missing inputs, observation age, retrieval timestamps and refresh failures, and retain prior valid data on failure.

The GDP and Fed equity-value FRED endpoints were verified for this scoped update on October 22, 2026. That result does not validate every other FRED series; earlier broader attempts encountered proxy/maintenance responses. SEC, additional Treasury data and EIA remain proposed source families rather than implemented connectors. No user authentication, hosting or cloud connector has been added. No source data is fabricated or uploaded.
