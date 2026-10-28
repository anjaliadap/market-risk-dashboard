# Dashboard readability audit

Verified locally on 2026-10-22 with Streamlit 1.66.1 and headless Microsoft Edge through Playwright. The existing application was updated in place. No financial calculations, workbook mappings/ingestion, database schemas or provider integrations were changed.

## Findings and fixes

- `dashboard/app.py` contained committed merge-conflict markers between the Excel integration and shared UI code. Reconciled both paths, retaining workbook synchronization and the existing full-history calculations. The application now starts normally.
- Broad inline and stylesheet overrides independently forced app/sidebar backgrounds, heading colors and button styles. Removed these conflicting rules. `.streamlit/config.toml` now locks the application to the requested light palette and explicitly configures the navy sidebar, white surfaces, dark text, semantic alert colors, dark-plum table headers and white header text.
- Streamlit captions inherited `opacity: 0.6`. A darker CSS foreground alone still failed contrast. A narrowly scoped caption rule now sets both the slate foreground and full opacity. Placeholders and disabled buttons have similarly scoped readable styling; disabled behavior is retained.
- Excel charts bypassed the existing shared chart wrapper. All workbook and independent-source figures now use one light Plotly renderer with explicit title, axis, legend, paper and hover-label colors. Existing unit formats and data arrays remain intact. Identity-based series colors stay consistent across sections; line styles provide additional differentiation. Explicit title positioning prevents clipping at the top of chart cards.
- Workbook tables had formatted strings left-aligned by the native grid. Explicit native column configuration now aligns numeric display columns right. Muted signed heatmaps retain plus/minus signs; saved checklist flags include “Signal present.” Totals/benchmarks use emphasis without incorrectly treating “Dow Jones Industrial Average” as a total row.
- Native JSON number coloring in administration failed contrast. The same diagnostics now appear in a readable, labeled table. Source metadata remains available in tables.
- Narrow viewports now stack column layouts rather than squeezing charts and controls. Financial grids retain their own horizontal scrolling without making the whole page overflow.

## Shared components

| File | Responsibility |
|---|---|
| `.streamlit/config.toml` | Authoritative palette; native theme, widgets, semantic alerts, table headers and sidebar |
| `dashboard/styles/theme.py` | Shared design tokens read from config, category headers, signed/status styles, financial grids and Plotly rendering |
| `dashboard/styles/institutional.css` | Scoped caption/placeholder/disabled-control fixes, metric surfaces, navigation states and narrow-layout rules; no generated class selectors |
| `dashboard/app.py` | Reconciled app startup and shared presentation for existing pages |
| `dashboard/excel_views.py` | Workbook charts/tables use shared renderers, explicit alignment and saved-signal labels |
| `tests/test_theme.py` | WCAG text-pair contrast, theme contract and presentation/data preservation tests |
| `scripts/audit_ui.py` | Full application browser/screenshot/contrast audit |
| `scripts/theme_preview.py`, `scripts/audit_widgets.py` | Clearly labeled UI-only native-control fixtures and browser interactions |

## Verification

**82 tests passed.** Ruff lint, formatting and `git diff --check` passed. Automated theme-pair tests require at least **4.5:1** for normal text: main and secondary text, sidebar, header buttons, table headers, semantic fills, category badges and the chart palette. The positive heatmap fill was lightened to `#F0F8F2` so the requested `#15803D` foreground meets this target.

The actual application was checked at **1440 × 1000** and **390 × 1000**. All **23 pages**, **46 page/viewport combinations**, completed with **zero detected text-contrast findings and zero page-wide horizontal overflows**. The browser audit exposed every lazily rendered chart and opened chart expanders: **49 rendered charts per viewport** (46 saved-workbook charts plus three assumption scenarios). Actual rendered chart axes and hover foregrounds matched dark slate on white. A real chart tooltip was also opened and inspected. Canvas-cell colors are covered by the configured native header colors and Styler/contrast tests; DOM text inspection cannot certify canvas text independently.

Pages verified in both viewports:

- Executive Overview.
- Market: Market Data, Bear Market, S&P vs Bonds, Valuation, S&P 500 Fundamentals, Margin Debt, S&P Relative, Gold to Oil, Banks, Bull vs Bear, VIX & Options, BTC, Housing and Energy.
- Macro: Recession and Consumer.
- AI: Supply, Demand, Financing and Forecasting.
- Research operations: Data Sources & System Status and Workbook Administration, including the real import controls.

The separate native-control browser pass exercised open dropdowns, the visible calendar picker, input values/placeholders, primary and disabled buttons, KPI cards, all four alert types and expanded details in both viewports, with zero detected contrast findings. It uses UI fixtures only; no app observations are replaced. The disabled control retained `disabled=True` with full-opacity slate text. Inactive calendar dates are excluded under the WCAG inactive-control exemption. Browser checks wait for loading transitions to settle.

Screenshots and machine-readable reports are private, under `EXCEL_ARTIFACT_DIR/ui_audit` (local AppData on this workstation), outside the OneDrive repository. Reports: `report.json`, `widget-report.json`, `hover-report.json`. Representative screenshots were manually reviewed for the overview, financial table/heatmap, desktop and narrow charts, dropdown/calendar and alerts. No screenshots or licensed financial values are committed.

These are targeted accessibility checks, not a complete WCAG certification. Dense grids may require internal horizontal scrolling on a phone. Existing pandas/NumPy timedelta deprecation warnings remain unrelated to presentation.

## Reproduce

```powershell
uv run streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

In another terminal, with Microsoft Edge installed:

```powershell
uv run --with playwright python -m scripts.audit_ui
```

For native controls, start the clearly labeled preview separately, then run its audit:

```powershell
uv run streamlit run scripts/theme_preview.py --server.address 127.0.0.1 --server.port 8502
uv run --with playwright python -m scripts.audit_widgets
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```
