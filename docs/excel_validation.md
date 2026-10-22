# Excel integration validation

Validation on 2026-10-22 used the supplied saved workbook and the sponsor Word document. The source workbook SHA-256 matched the audited source after import; the provider never saves it. The local workstation reads the Downloads source and stores immutable snapshots and sensitive audit artifacts under local AppData, outside the OneDrive repository.

- **53 automated tests passed**, including existing analytics/pages, two new AI pages, cache extraction from XLSX XML fixtures, invalid/error values, missing caches, unit/format and layout rejection, range/date contracts, content-based save detection, atomic last-valid retention, changed-during-validation rejection, moving reported-quarter markers, and populated dashboard updates.
- **Ruff lint and formatting passed**, along with `git diff --check`.
- **46 actual-workbook Plotly charts rendered** across all 18 mapped sections under Streamlit AppTest, with the populated administration page and full-app overview/navigation also checked. No browser screenshot or pixel-parity acceptance is claimed.
- **11 actual Excel arithmetic comparisons matched**: BTC market value/loan-to-value/debt coverage, implied gold/oil prices and upside/downside, reciprocal-yield valuation multiples, and both saved checklist fractions. The local report is in `EXCEL_ARTIFACT_DIR/excel_comparison.json`.
- The imported source's latest validated historical date is **2026-10-16**. Later forward estimates are excluded. This does not establish when Bloomberg was refreshed.

The workbook inventory reports two missing formula caches and 2,025 saved Bloomberg/BQL error messages. Initial gaps remain unavailable; a subsequent loss of a previously valid metric rejects the whole candidate snapshot. Sparse reported-quarter marker blanks are presentation metadata, not missing financial observations.

Remaining acceptance work: source formula/chart-range extensions, operator-maintained FINRA/Strategy/checklist inputs, resolution of BQL failures, complete Excel heatmap/table visual parity, independent Supply/productivity/semiconductor feeds, and sponsor review. Existing FRED live access, company Graph integration, data licensing for redistribution, hosting and production access controls were not validated or enabled. Streamlit AppTest emits a dependency-level pandas/NumPy timedelta deprecation warning; tests pass.
