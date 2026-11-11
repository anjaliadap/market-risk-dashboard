# Source coverage

Saved sponsor Excel is primary wherever mapped. All 19 substantive worksheets were audited; 46 charts and 8 tables are mapped across 18 sections. See [full source/range audit](excel_integration_map.md). Dates and source metadata accompany charts. Import time does not attest Bloomberg freshness.

| Section | Workbook coverage | Remaining dependency |
|---|---|---|
| Market Data | Equity/sector/rates/volatility/commodity snapshot; four breadth/flow charts | Authorized refresh, fixed chart endpoint review; Excel heatmap parity remains a visual refinement |
| Bear Market | Saved current/benchmark checklist, flags and score | Historical averages preserved; operator-dependent flags must be reviewed |
| S&P vs Bonds | Two cached spread/relative-multiple charts | Authorized refresh; sponsor calculation definitions retained |
| Valuation | Historical benchmarks and current saved values | Fixed assumptions retained; independent justified-P/E tool still available |
| S&P 500 Fundamentals | Four charts, including payouts and growth | Two BQL anchor caches absent; early Y/Y values unavailable |
| Margin Debt | Benchmarks and two ratio charts | FINRA manual input, hardcoded market cap, sponsor unit review |
| S&P Relative | Gold/WTI ratios and seven-year moving averages | Manual formula extensions; early rolling windows unavailable |
| Gold to Oil | Ratio/average/Brent chart and implied-price table | Fixed row-463 endpoints need authorized Excel maintenance |
| Banks | Net charge-offs chart | Sponsor Bloomberg population/definition |
| Bull vs Bear | Bull-minus-bear chart, decile table and auxiliary AAII chart | 2,025 BQL forward-return error texts; no Python fabrication or predictive claims |
| VIX & Options | Three charts and reference lines | Fixed chart endpoints clip longer source histories |
| BTC | Saved holdings/debt coverage table | Strategy holdings, debt/preferred and cost basis are manual |
| Housing | Six charts with series-specific dates and secondary axes | Bloomberg refresh and fixed endpoints |
| Energy | Five production/rig/efficiency charts | Futures vs spot and gas units preserved; EIA balances not connected |
| Recession | Saved 17-indicator checklist and Sahm chart | Manual states, saved flags and fixed warning line; no real-time vintages |
| Consumer | Three charts | Bloomberg refresh and source-specific denominators |
| Demand | Six company charts with reported/forward separation | Source estimates; additional productivity/semiconductor feeds not implemented |
| Financing | Four sponsor charts | Bloomberg refresh, company reported/forward estimates |
| Supply | No workbook source | Independent provider strategy documented; no verified connector |
| Forecasting | Existing analyst assumption tool | Scenarios distinct from reported company data |

Overview summarizes workbook coverage when a valid snapshot exists. Workbook Administration shows import health, missing values and manual dependencies. Data Sources & System Status retains independent FRED registry/job history. Optional independent FRED comparisons never merge with Excel under a shared metric identity.

FRED live integration remains unverified in this iteration; earlier attempts encountered proxy/maintenance responses. SEC, Treasury and EIA are proposed source families, not implemented integrations. No authentication, hosting or cloud connector has been added. No source data is fabricated or uploaded.
