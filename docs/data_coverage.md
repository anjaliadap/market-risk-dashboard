# Source coverage

Margin Debt, Bull vs Bear and BTC use public-source calculations by default. Each offers the imported workbook's saved view through its source selector when a validated snapshot exists. Other mapped sections retain the existing workbook-first behavior. Public observations and Excel snapshots remain separate; switching a view does not merge their metric identities or dates.

All 19 substantive sponsor worksheets were audited; 46 charts and 8 tables are mapped across 18 sections. See the [full source/range audit](excel_integration_map.md). Dates and source metadata accompany charts. Import time does not attest Bloomberg freshness, and a source retrieval time does not establish a new observation or release date.

**Public endpoint verification: October 22, 2026.** The scoped checks retrieved valid FINRA, AAII, Coinbase, GDP/Fed equity-value FRED and Strategy public website data. This is a historical verification date, not a claim that those endpoints or saved observations are current today. Other original sections' independent feeds were not re-audited in this scoped update. See [integration methodology](../INTEGRATION.md) and [verification notes](workbook_verification.md).

| Section | Default or existing coverage | Saved-workbook coverage / remaining dependency |
|---|---|---|
| Market Data | Equity/sector/rates/volatility/commodity snapshot; four breadth/flow charts | Authorized refresh, fixed chart endpoint review; Excel heatmap parity remains a visual refinement |
| Bear Market | Saved current/benchmark checklist, flags and score | Historical averages preserved; operator-dependent flags must be reviewed |
| S&P vs Bonds | Two cached spread/relative-multiple charts | Authorized refresh; sponsor calculation definitions retained |
| Valuation | Historical benchmarks and current saved values | Fixed assumptions retained; independent justified-P/E tool still available |
| S&P 500 Fundamentals | Four charts, including payouts and growth | Two BQL anchor caches absent; early Y/Y values unavailable |
| Margin Debt | Public FINRA monthly debit balances, historical references, quarterly GDP ratio and labeled Fed public-equity-value ratio | Optional saved benchmarks and two sponsor ratio charts remain available. Public quarterly equity value differs from monthly Wilshire 5000 capitalization; workbook FINRA and hardcoded market-cap inputs still require authorized maintenance. |
| S&P Relative | Gold/WTI ratios and seven-year moving averages | Manual formula extensions; early rolling windows unavailable |
| Gold to Oil | Ratio/average/Brent chart and implied-price table | Fixed row-463 endpoints need authorized Excel maintenance |
| Banks | Net charge-offs chart | Sponsor Bloomberg population/definition |
| Bull vs Bear | Public AAII history, bull-minus-bear chart, Excel-compatible percentiles/deciles, completed forward price-return comparisons, counts and positive-return frequencies | Optional saved spread chart, decile table and auxiliary AAII chart remain available. The audited workbook contains 2,025 BQL forward-return error texts. Public returns use weekly price closes, exclude dividends and differ from Bloomberg total returns; comparisons are descriptive and overlapping. |
| VIX & Options | Three charts and reference lines | Fixed chart endpoints clip longer source histories |
| BTC | Strategy public holdings, debt/preferred notional and portfolio average acquisition cost, combined with a timestamped Coinbase quote for the coverage table | Optional sponsor saved coverage table remains available. Company fields reconcile as one snapshot, with component dates distinct from quote time. Public delivery configuration changes may require provider maintenance; the imported workbook's company inputs remain manual. |
| Housing | Six charts with series-specific dates and secondary axes | Bloomberg refresh and fixed endpoints |
| Energy | Five production/rig/efficiency charts | Futures vs spot and gas units preserved; EIA balances not connected |
| Recession | Saved 17-indicator checklist and Sahm chart | Manual states, saved flags and fixed warning line; no real-time vintages |
| Consumer | Three charts | Bloomberg refresh and source-specific denominators |
| Demand | Six company charts with reported/forward separation | Source estimates; additional productivity/semiconductor feeds not implemented |
| Financing | Four sponsor charts | Bloomberg refresh, company reported/forward estimates |
| Supply | No workbook source | Independent provider strategy documented; no verified connector |
| Forecasting | Existing analyst assumption tool | Scenarios distinct from reported company data |

Overview summarizes workbook coverage when a valid snapshot exists. Workbook Administration shows import health, missing values and manual dependencies, including the three sections whose default views use public sources. Data Sources & System Status exposes the independent-source registry and ingestion jobs. The three public sections also show missing inputs, observation age, retrieval timestamps and refresh failures, and retain prior valid data on failure.

The GDP and Fed equity-value FRED endpoints were verified for this scoped update on October 22, 2026. That result does not validate every other FRED series; earlier broader attempts encountered proxy/maintenance responses. SEC, additional Treasury data and EIA remain proposed source families rather than implemented connectors. No user authentication, hosting or cloud connector has been added. No source data is fabricated or uploaded.
