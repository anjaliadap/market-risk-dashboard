# Implementation tracker

## Foundation
- [x] Python 3.12, locked dependencies, layered architecture
- [x] Grouped navigation: all 18 pages plus overview/status
- [x] SQLAlchemy observations/retrieval revisions/jobs and initial Alembic migration
- [x] FRED connector, strict parsing, bounded retries and timeout
- [x] Standalone refresh commands, bounded local background worker
- [x] Core analytics numerical tests and revision/failure tests
- [ ] Verify live official observations (blocked initially by network proxy 403; subsequent request returned FRED maintenance HTML)
- [ ] Complete normalized database entities, release calendars and cross-process leases
- [ ] Market Data full snapshot, sectors, heatmaps, aligned return comparisons
- [ ] Excel design verification (workbook absent)

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
