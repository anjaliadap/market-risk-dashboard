# Dedicated pages: Housing, Banks, Valuation, Consumer

Each page lives in `dashboard/sections/<page>.py` and exposes `render(ctx, render_section)`. Shared components (KPI tiles, lookback control, recession shading, indicator table, workbook helpers, cross-checks) are in `dashboard/sections/common.py`. Pure calculations are in `src/analytics/sectors.py` and unit-tested in `tests/test_sectors.py`. Page renders are exercised against an isolated synthetic database in `tests/test_sections.py`.

## Layout

Every page has four tabs:

1. **Sponsor workbook**: the existing mapped Excel charts and tables, unchanged. This tab comes first when a validated snapshot exists.
2. **Independent analytics**: FRED KPI tiles with Y/Y deltas, a 5Y/10Y/20Y/Max window, grouped charts with NBER recession shading, and derived measures labelled `DERIVED`.
3. **Indicators**: latest value, prior change, Y/Y, change vs 2019-Q4, percentile since 2000, source link and CSV export. Housing, Banks and Consumer add a **workbook vs FRED cross-check**: overlays on separate axes, never merged.
4. **Methodology & sources**: definitions, unit conventions, known gaps and the series registry.

Missing inputs leave tiles blank (`—`) and charts `UNAVAILABLE`. Values are never synthesized.

## Content

| Page | Independent series added | Derived analytics |
|---|---|---|
| Housing | MORTGAGE15US, HOUST1F, PERMIT1, MSACSR, MSPUS, MEHOINUSA646N, RHORUSQ156N (plus existing MORTGAGE30US, HOUST, PERMIT, HSN1F, CSUSHPINSA) | 30Y−10Y mortgage spread; monthly P&I on the median new-home price; payment-to-income; payment calculator with ±200 bp sensitivity; single-family starts/permits Y/Y; home-price growth |
| Banks | DRALACBS, CORALACBS, DRCCLACBS, CORCCACBS, DRCRELEXFACBS, DRBLACBS, CORBLACBS, DRSFRMACBS, DRTSCILM, DRTSCLCC, TOTLL, DPSACBW027SBOG | Credit stress monitor (Q/Q, Y/Y, vs 2019-Q4, peak, percentile, z-score); loan and deposit growth; loan-to-deposit ratio |
| Valuation | DFII10, NCBEILQ027S, CP (plus existing DGS10, T10YIE, GDP, SP500) | Earnings yield and gaps vs nominal/real 10Y; implied perpetual growth; P/E consistent with a premium over the real yield; nonfinancial equity value / GDP with ±1σ bands; profits / GDP; justified-P/E sensitivity heatmap |
| Consumer | UMCSENT, DSPIC96, PCEC96, RSAFS, CES0500000003, MDSP, CDSP (plus existing PSAVERT, TDSP, TOTALSL, REVOLSL, NONREVSL, CPIAUCSL, UNRATE; shares card credit series with Banks) | Real income vs spending growth; real wage growth (AHE Y/Y − CPI Y/Y); debt-service decomposition; credit growth by type; card stress; sentiment vs unemployment |

## Valuation P/E input

The P/E defaults to the workbook's saved `Valuation!F11` (= 1/F9) when a validated snapshot exists. Otherwise the analyst must enter it, and the page assumes no multiple until then. Cost of equity and payout are labelled assumptions.

## Ingestion

New series use the existing registry categories, so the standard commands pick them up:

```sh
uv run python -m scripts.refresh_market   # Market, Energy, Housing
uv run python -m scripts.refresh_macro    # Recession, Consumer
```

FRED live access has not been verified from this development environment (proxy 403). Verify on a workstation with network access before relying on the pages.

## Known limitations

- Existing-home sales, inventory and prices (NAR) remain workbook-only.
- FDIC QBP items (NIM, reserves, unrealized losses) are not connected. FRED's FFIEC NIM/ROA series are discontinued and excluded.
- Payment-to-income uses annual nominal median household income, published with a lag of about 9 months and held for up to 24 months.
- Equity value / GDP uses Z.1 nonfinancial corporate equities (includes closely held, excludes financials). It is not the Wilshire-based indicator.
- UMich sentiment is redistributed on FRED with a licensing delay.

# Dedicated pages: Recession, VIX & Options, Supply, Demand, Financing

These pages use the same structure as above (`dashboard/sections/<page>.py`, `render(ctx, render_section)`). Shared checklist, workbook-table and analyst-log helpers are in `dashboard/sections/extras.py`. Rules and calculations are in `src/analytics/signals.py` (unit tests: `tests/test_signals.py`). Page renders are tested in `tests/test_ai_macro_sections.py`, including a synthetic workbook snapshot built from the real mapping contract.

## Rule-based checklists

The sponsor's Recession tab is a red-flag checklist. The Demand and Financing tabs carry text-only "Tracker" warning lists (Demand!B2:B5, Financing!B2:B6) with no status column. Each is now an explicit, automated rule set. The checklist table shows the warning reading, current reading, status, RED / Not red / UNAVAILABLE, as-of date, source and rule text. Score = red ÷ **evaluated** items. Unavailable items are excluded from the denominator and never assumed green. Each checklist exports to CSV.

| Page | Items | Primary source | Fallback |
|---|---|---|---|
| Recession | All 17 sponsor items (inflation, curve, inventory/sales, cyclicals, employment, claims, LEI, IP, personal income, output gap, real M2, wages, PMI, 10Y − GDP, credit, sentiment, equities) | FRED, with thresholds from the sponsor's notes column | LEI and PMI are licensed and use the sponsor's saved manual flag (column G) when a snapshot exists. The sponsor's saved status and flag appear beside every row. |
| Demand | Slowing AI sales vs capex; slowing/stalling productivity; declining semiconductor billings momentum | Workbook (hyperscaler sales vs capex, reported quarters only); FRED OPHNFB; FRED IPG3344S as a billings proxy | — |
| Financing | Capex > CFOps; Tech HY spreads; leveraged cloud underperformance (ORCL, CRWV); lower liquidity / AI lab IPO delays | Workbook for company-specific items; FRED NFCI + SLOOS (DRTSCILM) proxy for liquidity | Tech HY falls back to FRED HY − IG OAS, labelled as a proxy |
| VIX & Options | Signal board: VIX ≥ 30, VIX/VIX3M > 1, VIX ≥ 1Y 90th percentile, implied < realized, put/call ≥ 90th percentile | FRED; put/call from the workbook | — |
| Supply | Bottleneck board: electrical-equipment and computer/electronics backlog above the 2015–19 maximum, transformer/turbine PPI > 10% Y/Y, semis utilization > 80% | FRED (Census M3, BLS PPI, Fed G.17) | — |

The Recession page also evaluates the checklist **as of each prior NBER recession start**, plus any events imported with `scripts.import_historical_events`, on current revised data. This is descriptive, not a real-time backtest.

## Content

| Page | Independent series added | Derived analytics |
|---|---|---|
| Recession | T10Y3M, SAHMREALTIME, RECPROUSM156N, RETAILIRSA, DGORDER, A007RL1Q225SBEA, A011RL1Q225SBEA, W875RX1, GDPC1, GDPPOT, M2REAL, IC4WSA (plus existing CPI, UNRATE, ICSA, INDPRO, GDP, DGS2/10, HY OAS, SP500, USREC; UMCSENT and AHE from Consumer) | 17-item checklist; official vs current-vintage Sahm with 0.5 trigger; curve spreads; output gap; cyclical components vs averages since 2000; Sahm cross-check against the workbook's SAHMRLRT |
| VIX & Options | VXVCLS, VXNCLS, OVXCLS, GVZCLS | Regime bands; VIX/VIX3M term structure; VIX − 21-day realized S&P vol; days since VIX ≥ 30; cross-asset vol; workbook put/call, VIX-call and SPX-put percentiles, z-scores and 4-week averages |
| Demand | OPHNFB, PRS85006092, ULCNFB, IPG3344S, CAPUTLG3344S, A34SNO, A34SVS, PCU33443344, A679RL1Q225SBEA, A679RC1Q027SBEA | Productivity Y/Y, 2Y/5Y annualized, period CAGRs (2000–07, 2007–19, 2019–now, 2022-Q4–now); semiconductor 3MMA momentum, 24-month momentum peak, book-to-bill; IT investment share of GDP; workbook capex-minus-sales growth by hyperscaler |
| Financing | BAMLC0A0CM, BAMLC0A4CBBB, BAMLH0A3HYC, NFCI, BCNSDODNS (plus HY OAS, DRTSCILM, GDP) | HY − IG; nonfinancial corporate debt/GDP; workbook TTM capex/CFOps by company; quarterly and trailing-4Q funding gap (capex − CFOps) |
| Supply | A35SUO, A35SVS, A34SUO, PCU335311335311, PCU333611333611, IPG2211S (plus A34SVS, CAPUTLG3344S) | Months of backlog (unfilled ÷ shipments); grid-equipment PPIs rebased to Dec 2019; analyst logs |

## Analyst-sourced data (Supply, Demand)

Several items have no free machine-readable feed: GPU rental prices (chip × on-demand / spot / contracted), data-center capacity (operational / under construction / planned MW), vacancy and available supply, lead times, and SIA/WSTS semiconductor billings. Each has an entry form and CSV import. Every record needs a source URL, a date that is not in the future and a non-negative value. Records are stored as append-only `research_records` rows (`kind = analyst:<dataset>`) and can be charted and exported. They are never scraped, interpolated or estimated. The Supply layout is a proposal to review with the sponsor, who asked to see ideas before the section is built out.

## Ingestion

`refresh_ai` now ingests `AI`-category series. `refresh_macro` picks up the Recession additions, and `refresh_market` picks up the VIX and credit-spread additions:

```sh
uv run python -m scripts.refresh_market
uv run python -m scripts.refresh_macro
uv run python -m scripts.refresh_ai
```

All 37 new FRED series were retrieved successfully on 2026-11-08.

## Known limitations

- The workbook saved on 2026-10-23 cannot be imported. Its Bloomberg cells (e.g., `Market Data!AK4` and the Demand/Financing BQL ranges) hold `#NAME?` because it was saved without the add-in. Re-save it after a Bloomberg refresh. Until then, workbook-dependent tracker items show UNAVAILABLE.
- Conference Board LEI, ISM/S&P Global PMI, SIA/WSTS billings, CBOE put/call, MOVE and GPU-price indices are licensed or not published as free series. No substitute is claimed except where labelled as a proxy.
- FRED redistributes about three years of ICE BofA OAS history, so credit rules are change-based or refer only to that window.
- Productivity comparisons across periods are descriptive and cannot attribute changes to AI.

# Dedicated pages: Momentum, FC Data, Failure Candidates, S&P Relative

These follow the 2026-11 workbook (`updated-PCM-Material`) and its Process document. Navigation now follows the workbook tab order. A new **Empirical** group comes first (Momentum = tab "Mo", FC Data, Failure Candidates), then Market, Macro and AI. Within AI, Demand and Financing follow the tabs; Supply and Forecasting have no tab and come last. Pure calculations are in `src/analytics/empirical.py` (tests: `tests/test_empirical.py`). Page renders against a synthetic snapshot built from the real mapping are tested in `tests/test_empirical_sections.py`.

The three Empirical tabs are sponsor research data, updated manually each month, with no public equivalent. Their pages use the tabs **Sponsor workbook / Analytics / Data & export / Methodology & sources** and show UNAVAILABLE until a snapshot is imported. S&P Relative keeps the standard four tabs because it has an independent FRED cross-check.

| Page | Sponsor workbook (mapped) | Analytics added |
|---|---|---|
| Momentum | Mo!E4:AGH7: score, average, 70 threshold; trailing-change table AGJ:AGM | Signal board (≥ threshold, top decile, building); history with shaded threshold episodes and labelled peaks; episode table; S&P 500 3/6/12M price returns after each upward crossing vs all months, using the saved monthly S&P 500 from S&P Relative |
| FC Data | 14 charts: 11 sectors + Big Growers, Expensive, Leveraged Borrowers (F:UU, from 1980), recession bars from row 21 | Multi-group comparison with recession shading; heatmap of recent months; statistics recomputed with the sponsor's definitions (mean, sample SD, z, 1/3/6/12M changes) and checked against the saved Failure Candidates summary |
| Failure Candidates | AC5:AS20: failure share, mean, SD from mean, trailing changes, OPP/Patient/S&P weights, relative weight, OW position | Overweight/Risk rules re-applied to the inputs with a mismatch warning; count and weight of each portfolio in 'Risk' sectors; color-coded matrix as in the sponsor sheet; active weight vs z-score quadrant; latest vs mean |
| S&P Relative | Gold block B:H and oil block J:P (ratio, 7Yr MA, current), plus underlying monthly S&P 500, gold and WTI CL1 | Distance from 7-year average; percentiles and long-run median bands; S&P 500 / gold / oil implied by a return to the average; FRED S&P 500 ÷ WTI spot cross-check |

## Workbook changes found in the 2026-11 file

- **S&P Relative**: the oil block moved one column right (J dates, M ratio, N MA), "Current" lines were added (H, P), and rows now end at 926. The mapping is updated to match.
- **Recession**: the checklist moved up three rows (B4:H53) and the Sahm chart now uses S5:U132, newest first, from 2015. The mapping and `RECESSION_ROWS` are updated. The sponsor's definitions also changed (Core inflation, Atlanta Fed wage tracker, BEA personal income), but the independent rules have **not** yet been changed to match.
- **VIX & Options**: put/call cells now also use `#,##0.00` / `0.00`. These formats are allowed.
- **Still blocking a full import** (import is all-or-nothing): Financing row 3 now holds text period labels ("2017 Q4 (Rep)") instead of dates, which needs importer support for label-based quarters; Bear Market (`B7`) and Bull vs Bear (`W3`) layouts changed and need their owners' mapping updates.
- FC Data's Industrials chart in Excel plots G6:UU6 against F3:UU3 (one-column offset). The mapping uses F6:UU6 so that each value keeps its own date.
