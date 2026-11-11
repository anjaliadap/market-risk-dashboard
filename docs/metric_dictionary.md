# Metric dictionary

Raw series definitions, units, sources, category and frequency are in `config/series.json`. All charts retain those units. Available calculation functions:

| Measure | Formula / convention |
| --- | --- |
| Price return | 100 × (end/start − 1), positive baseline required |
| Log return | ln(price / prior price), positive prices |
| Yield change | 100 × (yield percent − baseline yield percent), bp |
| Moving average | trailing full-window arithmetic mean |
| Range proximity | 100 × (latest / trailing high or low − 1) |
| Sector outperformance | count and share strictly above benchmark |
| Relative performance | exact-date numerator / denominator |
| Correlation | rolling correlation of exact-date simple returns |
| Volatility | rolling sample standard deviation × sqrt(annual sessions) × 100 |
| Drawdown | 100 × (price / cumulative maximum − 1) |
| Percentile | empirical fraction <= observation × 100 |
| Decile | ceiling(percentile / 10), bounded 1–10 |
| Earnings-yield spread | 100 / P-E minus Treasury yield percent; not ERP |
| Justified P/E | (1 − retention) / (cost of equity − growth) |
| Margin debt/GDP | same-unit debt / GDP; stock/annualized-flow interpretation required |
| Capex/OCF | capex / operating cash flow; negative/zero denominators unavailable |
| Scenario FCF | assumed OCF compound path minus assumed capex path |

Calculation availability does not imply input-data availability. No modeled equity risk premium, realized company data forecast or recession probability is implemented.
