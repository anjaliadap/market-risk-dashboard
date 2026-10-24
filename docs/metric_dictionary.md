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
| Y/Y (dedicated pages) | vs last observation on/before date − 12 months; tolerance daily 7, weekly 10, monthly 20, quarterly 45, annual 400 days |
| Baseline vs 2019-Q4 | value on/before 2019-12-31 within one period (quarterly FRED dates are quarter starts) |
| Mortgage P&I | principal × r / (1 − (1 + r)^−n), r = annual rate/12, n = months; excludes tax, insurance, PMI |
| Payment-to-income | 12 × monthly P&I / annual median household income × 100 |
| Mortgage spread | PMMS 30Y − 10Y CMT within 7 days, bp |
| Loan-to-deposit | H.8 loans and leases / deposits × 100 |
| Implied growth | cost of equity − payout / P-E × 100 |
| P/E for premium | 100 / (10Y real yield + premium) |
| Equity value / GDP | Z.1 NCBEILQ027S (millions) × 0.1 / GDP (billions SAAR) |
| Profits / GDP | CP (billions SAAR) / GDP × 100 |
| Real wage growth | AHE Y/Y − CPI-U Y/Y (approximation) |
| Z-score | (latest − mean) / sample SD over retained history |

Calculation availability does not imply input-data availability. No modeled equity risk premium, realized company data forecast or recession probability is implemented.
