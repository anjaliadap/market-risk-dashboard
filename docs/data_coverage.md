# Coverage and external dependencies

**No live series is verified yet: FRED requests initially received proxy HTTP 403; latest requests reach FRED but receive HTTP 200 maintenance HTML, not CSV.** Parsing and calculations are tested independently with synthetic test fixtures, never displayed as real observations.

| Section | Status | Current capability / remaining requirement |
| --- | --- | --- |
| Market Data | Implemented but requires network access; partial | FRED index, rates, VIX, spot energy; missing other indices, sectors, MOVE and metals |
| Bear Market | Not yet implemented analytics | Input viewer; historical peaks and risk checklist pending |
| S&P vs Bonds | Not yet implemented | Treasury history; dated index earnings needed |
| Valuation | Implemented and verified calculation only | Assumption-driven justified P/E; observed valuations awaiting licensed data |
| S&P 500 Fundamentals | Awaiting licensed data | No official index aggregate feed |
| Margin Debt | Not yet implemented | FINRA history, unit/date alignment |
| S&P Relative | Not yet implemented page analytics | Inputs partially connected; ratio UI pending |
| Gold to Oil | Not yet implemented | Gold feed missing |
| Banks | Not yet implemented | FDIC connector pending |
| Bull vs Bear | Awaiting licensed data | AAII permission/history and timing-aware studies |
| VIX & Options | Partial; network blocked | VIX connector; options/MOVE feeds missing |
| BTC | Research-dependent | Permitted exchange/aggregation source selection |
| Housing | Partial; network blocked | FRED housing; several industry feeds missing |
| Energy | Partial; network blocked | Spot prices; EIA balances/storage pending |
| Recession | Partial; network blocked | FRED inputs; checklist, vintages and comparisons pending |
| Consumer | Partial; network blocked | FRED consumer histories; interpretation and sentiment pending |
| Demand | Not yet implemented | SEC and industry supply/demand integrations pending |
| Forecasting | Implemented and verified scenario calculation only | Deterministic assumption-driven scenarios; company fundamentals absent |

Executive Overview aggregates selected stored raw observations. System Status exposes source registry and ingestion job errors. No proxy data is silently substituted. The Excel workbook was not supplied; its exact formatting and moving-average meaning cannot be verified.
