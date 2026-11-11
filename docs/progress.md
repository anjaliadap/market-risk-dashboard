# Implementation tracker

## Foundation
- [x] Python 3.12, locked dependencies, layered architecture
- [x] Existing grouped navigation preserved; Supply, Financing and Workbook Administration added
- [x] SQLAlchemy observations/retrieval revisions/jobs and initial Alembic migration
- [x] FRED connector, strict parsing, bounded retries and timeout
- [x] Standalone refresh commands, bounded local background worker
- [x] Core analytics numerical tests and revision/failure tests
- [ ] Verify live official observations (blocked initially by network proxy 403; subsequent request returned FRED maintenance HTML)
- [ ] Complete normalized database entities, release calendars and cross-process leases
- [ ] Market Data full snapshot, sectors, heatmaps, aligned return comparisons
- [x] Supplied workbook/Word audit and review of 31 embedded illustrations

## Required sections
- [ ] Market Data: complete full specification; see data_coverage.md for current partial functionality
- [ ] Bear Market: complete full specification; see data_coverage.md for current partial functionality
- [ ] S&P vs Bonds: complete full specification; see data_coverage.md for current partial functionality
- [ ] Valuation: complete full specification; see data_coverage.md for current partial functionality
- [ ] S&P 500 Fundamentals: complete full specification; see data_coverage.md for current partial functionality
- [ ] Margin Debt: complete full specification; see data_coverage.md for current partial functionality
- [ ] S&P Relative: complete full specification; see data_coverage.md for current partial functionality
- [ ] Gold to Oil: complete full specification; see data_coverage.md for current partial functionality
- [ ] Banks: complete full specification; see data_coverage.md for current partial functionality
- [ ] Bull vs Bear: complete full specification; see data_coverage.md for current partial functionality
- [ ] VIX & Options: complete full specification; see data_coverage.md for current partial functionality
- [ ] BTC: complete full specification; see data_coverage.md for current partial functionality
- [ ] Housing: complete full specification; see data_coverage.md for current partial functionality
- [ ] Energy: complete full specification; see data_coverage.md for current partial functionality
- [ ] Recession: complete full specification; see data_coverage.md for current partial functionality
- [ ] Consumer: complete full specification; see data_coverage.md for current partial functionality
- [ ] Demand: complete full specification; see data_coverage.md for current partial functionality
- [ ] Forecasting: complete full specification; see data_coverage.md for current partial functionality

## Integration / acceptance
- [ ] Real-data integrations verified
- [ ] Full metric-level implementation/source coverage
- [ ] Historical point-in-time comparisons and overlap-aware studies
- [ ] SEC financial statement normalization and AI supply/demand
- [ ] All sponsor acceptance criteria and visual review

No phase is marked complete merely because a page renders. This iteration establishes a tested foundation; the full project remains in progress.

## Saved Excel integration
- [x] Audit all 23 sheets (19 substantive); formula/cache/manual input and chart dependency inventory
- [x] Versioned centralized mapping: 46 charts, 8 tables, 18 sections
- [x] Reusable saved-value provider with formula/source metadata
- [x] Immutable local database snapshots, atomic publication and last-valid retention
- [x] Stable-save detection, content hashes, background worker and optional CLI watcher
- [x] Administration page, reimport, coverage/manual dependencies and error reporting
- [x] Plotly combinations, separate axes/dates, reported-quarter markers and percent formats
- [x] 11 arithmetic comparisons against actual saved Excel outputs matched
- [x] Tests for caches, invalid data, layout/units, snapshot regression, save settling and chart updates
- [ ] Sponsor visual acceptance and full heatmap/table presentation parity
- [ ] Bloomberg refresh attestation and source workbook error/manual dependency resolution
- [ ] Approved range/formula extensions beyond fixed chart endpoints
- [ ] Independent Supply, productivity, semiconductor, SEC and EIA connectors

Older full-specification items remain unchecked pending acceptance and source gaps. Saved Excel coverage supersedes the earlier FRED-only coverage; see data_coverage.md.
