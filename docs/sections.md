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
