# Workbook integration verification

Verified on October 22, 2026 against repository base
`f89f4d00cccaddf6a329fba779cce0c370332273`.

## Automated checks

- 208 tests passed, including the original application tests and new provider,
  calculation, atomic ingestion, populated-page and CSV-export checks.
- Ruff lint and formatting checks passed.
- Test data are isolated fixtures. The supplied workbook's cached values were used
  independently as formula controls, not as live provider replacements.
- Current locked Pandas/NumPy/Streamlit combinations emit dependency deprecation
  warnings; there were no failed checks or application exceptions.

## Live source verification

All required public-source refresh groups completed successfully, without a user
API key or Bloomberg:

| Input | Verified coverage or snapshot |
|---|---|
| FINRA debit balances | 357 monthly observations, January 1997–September 2026 |
| Nominal GDP via FRED | 106 quarters, 2000 Q1–2026 Q2 |
| Fed public equity market value via FRED | 118 quarters, 1997 Q1–2026 Q2 |
| AAII sentiment and reported weekly closes | 2,046 surveys, 1987–October 22, 2026 |
| Coinbase spot | Actual UTC last-trade timestamp retained |
| Optional Coinbase completed daily closes | 4,112 days, July 20, 2015–October 21, 2026 |
| Strategy holdings, debt, preferred, average cost | Coherent company datasets dated October 19, 2026 |

Sources and the exact endpoints are recorded in `config/workbook_series.json` and
the provider modules. Public delivery identifiers used by Strategy are read-only
website configuration. No login-gated export or user credential was used.

The command `python -m scripts.refresh_workbook_sections` completed all groups
successfully. Repeated ingestion retained unchanged values and added only revised
observations or timed quote snapshots. The due-only command observed throttling.

## Financial formula controls

Using the supplied workbook's inputs:

- GDP ratio: June 2026 debt of USD 1,502.072 billion divided by nominal GDP of
  USD 32,563.03 billion gives 4.6128139795%; the 106-quarter arithmetic mean is
  2.4276636259%, matching the workbook.
- All 2,045 cached sentiment percentiles matched the Excel calculation after
  enforcing integer-safe half-up rounding. Tie and decile boundary tests passed.
- BTC value, claims, LTV, coverage, 1:1 price, downside and gain/loss matched the
  workbook's cached control inputs. These snapshot figures were not embedded as
  production inputs.
- Public alternatives are deliberate: quarterly Fed market capitalization differs
  from monthly Wilshire, and weekly S&P 500 price returns exclude dividends and
  differ from Bloomberg total returns. Current public outputs need not match old
  cached workbook results.

## Dashboard and file export

All three populated pages were inspected in the local browser. The new views
show expandable histories, source/status detail, readable charts and tables,
current-decile highlighting and the BTC threshold/downside highlights. Narrow
views stack the charts and metrics; table horizontal scrolling retains columns.
Populated-page tests also verify missing inputs, stale quotes, source failures
and coherent company revisions.

The real saved-data export completed with:

- 118 rows in `margin_debt.csv`, including 106 GDP-ratio and 118 equity-proxy rows;
- 7 historical reference/summary rows;
- 2,046 rows in `bull_vs_bear.csv` and 10 decile rows;
- 10 rows in `btc.csv`;
- provenance, units, raw observation labels, reference-period ends, component
  dates, source quote times and SHA256 checksums in the manifest.

Incomplete future return periods remain blank. Missing/invalid sources and write
failures leave the previously published export generation intact. Exports and
downloaded raw source histories used for verification are excluded from this
source-code distribution.

## Practical limits

The three requested sections are implemented. Other sections of the original
project retain their pre-existing coverage. Live refresh requires a running app
or a scheduler on the deployment host; no hosted service or scheduled job is
installed by this package. Data remain subject to publication delays, source
revisions, endpoint changes and publisher terms. Saved retrieval vintages do not
establish point-in-time publication histories for trading backtests.

## Latest repository integration — November 12, 2026

The public-source update was combined with main commit
`8cde9c457357da1fa61d62be811ac46cb8282cd8`. Existing saved-workbook ingestion,
Workbook Administration, database import snapshots, migration 0002, themes and
all other section routes were retained. A source selector on the three target
pages defaults to public data and also opens the imported workbook view.

The combined project passed 256 tests with network connections blocked and an
isolated temporary database. Ruff checks passed. The November 12 checks validate
the code integration; the live endpoint verification described above remains
dated October 22, 2026.
