# Excel integration audit and mapping

Audit completed before provider implementation. The supplied Word document is the authority for chart intent and layout; workbook chart references are the authority for saved series. No source workbook is modified. Full cell/formula/cache/font inventory is local-only in `EXCEL_ARTIFACT_DIR/workbook_audit.json` (defaults to local AppData, outside the synchronized project); no cached financial values or document images are committed.

Workbook SHA-256 at audit: `73612a4d400b796238cd11f4cd81d203574d10521b672627aa4f18583a4af523`. 23 worksheets, 19 substantive sheets, no external workbook links. Divider/cache sheets: Market>, Macro>, AI>, PB_CACHE_JS. Bloomberg XLL references are add-in calls, not external-workbook links.

## Findings and refresh contract

- Almost all formulas have saved caches. Fundamentals L23/Q23 have no cache. Bull vs Bear has 2,025 error-text cells in its forward-return area, despite no native Excel error-typed cells. Errors encoded as text must also be rejected.
- Cached values establish what Excel last saved, not when Bloomberg was refreshed. TODAY(), file name, modification time and successful import are never refresh attestations. Several dates extend into forward estimate periods; they are not latest observed dates.
- Readiness requires authorized Excel/Bloomberg refresh, formula extension where noted, recalculation and save. Python never evaluates XLL/BQL/BDH/BDP or Excel formulas. Missing formula caches remain unavailable.
- Chart ranges are deliberately explicit. Source spills and worksheet used ranges often extend past chart endpoints; auto-extending these could change historical benchmarks or forecasts. Central mapping review is required after layout/endpoint changes.
- Tables retain raw sponsor values and number formats. Percent fractions are displayed using their Excel formats, not guessed scaling. Undated snapshots remain explicitly undated. Native errors, text errors, missing caches and manual inputs are reported.
- Recession and bear-market saved checklist flags may lag manual states. Saved scores are displayed as sponsor outputs, not recalibrated predictions. Do not infer financial signals from red font (which also denotes manual inputs).

## Section coverage

Existing Forecasting remains an assumption tool. Add Financing (present in sponsor files) and Supply (no workbook sheet) without removing existing pages. Overview summarizes section coverage. FRED remains independent fallback; Treasury, SEC and EIA are not currently implemented connectors.

`config/excel_mapping.json` is the executable, versioned contract. Each chart series has a named metric ID, sheet, values/date ranges, units/number format, type and axis. Missing category references in combo charts are resolved to their own adjacent date columns, not borrowed from a differently sampled series. These inferences are marked for review.

## Market Data

Used range: A1:AY5687. Inventory: `{"hardcoded": 36383, "bloomberg": 296, "formula": 4265, "dated_cells": 16055}`.

Authorized Bloomberg refresh/save; snapshot TODAY() dates are calculation dates, not release dates. Sector breadth is constituent breadth, not index distance to DMA. Futures prices must not be labeled spot.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| % of S&P 500 Trading > 50-DMA | % | AL4:AL5686 | AK4:AK5686 | LineChart / left |
| % of S&P 500 Trading > 200-DMA | % | AO4:AO5426 | AN4:AN5426 | LineChart / left |
| % of S&P at 52Wk High vs Low | High | AR4:AR4225 | AQ4:AQ4225 | BarChart / left |
| % of S&P at 52Wk High vs Low | Low (Formula for Chart) | AT4:AT4225 | AQ4:AQ4225 | BarChart / left |
| SPY Flows | $ | AW4:AW4225 | AV4:AV4225 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| E | 34 | E4 / E54 | E54 | `=_xll.BDP($Y4,"CURRENT_TRR_YTD")/100` |
| J | 17 | J4 / J21 | J21 | `=_xll.BDP(Y4, "PCT_MEMB_PX_GT_50D_MOV_AVG")/100` |
| L | 17 | L4 / L21 | L21 | `=_xll.BDP($Y4,"PCT_MEMBERS_WITH_NEW_52_WK_LOWS")/100` |
| O | 1 | O36 / O36 | O36 | `=_xll.BDH($Y36, "LAST PRICE", TEXT(T36, "YYYYMMDD"), TEXT(T36, "YYYYMMDD"), "days=a", "fill=p")/100` |
| T | 1 | T36 / T36 | T36 | `=DATE(YEAR(TODAY())-1, 12, 31)` |
| AK | 1 | AK4 / AK4 | AK5687 | `=_xll.BDH("SPX Index", "PCT_MEMB_PX_GT_50D_MOV_AVG", "2005-01-01", TODAY(), "PER=D","cols=2;rows=5684")` |
| AN | 1 | AN4 / AN4 | AN5427 | `=_xll.BDH("SPX Index", "PCT_MEMB_ABOVE_MOV_AVG_200D", "2006-01-01", TODAY(), "PER=D","cols=2;rows=5424")` |
| AQ | 1 | AQ4 / AQ4 | AQ4226 | `=_xll.BDH("SPX Index", "PCT_MEMBERS_WITH_NEW_52W_HIGHS, PCT_MEMBERS_WITH_NEW_52_WK_LOWS", "2010-01-01", TODAY(), "Per=D","cols=3;rows=4223")` |
| AV | 1 | AV4 / AV4 | AV703 | `=_xll.BDH("SPY US Equity", "FUND_FLOW", "2024-01-01", TODAY(),"cols=2;rows=700")` |
| B | 32 | B4 / B54 | B54 | `=_xll.BDP(Y4,"SECURITY_NAME")` |
| D | 33 | D4 / D54 | D54 | `=_xll.BDP(Y4,"LAST PRICE")` |
| F | 34 | F4 / F54 | F54 | `=_xll.BDP($Y4,"CHG_PCT_1M")/100` |
| G | 34 | G4 / G54 | G54 | `=_xll.BDP($Y4,"CHG_PCT_3M")/100` |
| H | 34 | H4 / H54 | H54 | `=_xll.BDP($Y4,"CHG_PCT_6M")/100` |
| I | 34 | I4 / I54 | I54 | `=_xll.BDP($Y4,"CHG_PCT_1YR")/100` |
| K | 17 | K4 / K21 | K21 | `=_xll.BDP($Y4,"PCT_MEMB_ABOVE_MOV_AVG_200D")/100` |
| M | 17 | M4 / M21 | M21 | `=_xll.BDP($Y4,"PCT_MEMBERS_WITH_NEW_52W_HIGHS")/100` |
| P | 1 | P36 / P36 | P36 | `=_xll.BDH($Y36, "LAST PRICE", TEXT(U36, "YYYYMMDD"), TEXT(U36, "YYYYMMDD"), "days=a", "fill=p")/100` |
| Q | 1 | Q36 / Q36 | Q36 | `=_xll.BDH($Y36, "LAST PRICE", TEXT(V36, "YYYYMMDD"), TEXT(V36, "YYYYMMDD"), "days=a", "fill=p")/100` |
| R | 1 | R36 / R36 | R36 | `=_xll.BDH($Y36, "LAST PRICE", TEXT(W36, "YYYYMMDD"), TEXT(W36, "YYYYMMDD"), "days=a", "fill=p")/100` |
| S | 1 | S36 / S36 | S36 | `=_xll.BDH($Y36, "LAST PRICE", TEXT(X36, "YYYYMMDD"), TEXT(X36, "YYYYMMDD"), "days=a", "fill=p")/100` |
| U | 1 | U36 / U36 | U36 | `=Z36-30` |
| V | 1 | V36 / V36 | V36 | `=Z36-(30*3)` |
| W | 1 | W36 / W36 | W36 | `=Z36-(30*6)` |
| X | 1 | X36 / X36 | X36 | `=Z36-365` |
| Z | 22 | Z4 / Z36 | Z36 | `=TODAY()` |
| AT | 4222 | AT4 / AT4225 | AT4225 | `=-AS4` |

Red-font hardcoded cells: 0; examples ``. All constants and full formulas are retained in the local inventory for operator review.

## Bear Market

Used range: A1:BQ114. Inventory: `{"hardcoded": 498, "formula": 271, "bloomberg": 38, "dated_cells": 27}`.

D8:D21 current, E8:E21 historical averages (linked to row 22, preserve them), G8:G21 explicit direction rules; F8:F21 saved flags. D23=14 denominator. Historical peaks and IPO inputs are sponsor assumptions. Never infer red flags from font colors.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| AZ | 11 | AZ13 / AZ26 | AZ26 | `=_xll.BDP($AZ4,"CUST_TRR_RETURN_HOLDING_PER", $AZ$2, BC13, $AZ$3, BB13)/100` |
| BL | 1 | BL3 / BL3 | BL114 | `=_xll.BQL("filter(equitiesuniv(['active','primary']), cntry_of_domicile=='US')", "sum(#ipo().value)/1B as #US_IPO_Proceeds_YTD_USD_bn", "#ipo=dropna(equity_offerings(type=IPO, effe` |
| BM | 1 | BM2 / BM2 | BM114 | `=SUM(BM4:BM1048576)` |
| BO | 4 | BO3 / BO6 | BO6 | `=BM2` |
| AY | 11 | AY13 / AY26 | AY26 | `=_xll.BDP($AY4,"CUST_TRR_RETURN_HOLDING_PER", $AZ$2, BC13, $AZ$3, BB13)/100` |
| BA | 11 | BA13 / BA26 | BA26 | `=_xll.BDP($BA4,"CUST_TRR_RETURN_HOLDING_PER", $AZ$2, BC13, $AZ$3, BB13)/100` |
| BP | 1 | BP4 / BP4 | BP4 | `=DATE(YEAR(TODAY())-1, 12, 31)` |
| D | 16 | D8 / D24 | D24 | `=S26` |
| Q | 4 | Q22 / Q26 | Q26 | `=AVERAGE(Q8:Q19)` |
| V | 4 | V22 / V26 | V26 | `=AVERAGE(V8:V19)` |
| AK | 4 | AK22 / AK26 | AK26 | `=AVERAGE(AK8:AK19)` |
| AS | 4 | AS22 / AS26 | AS26 | `=AVERAGE(AS8:AS20)` |
| BB | 1 | BB26 / BB26 | BB26 | `=TODAY()` |
| BD | 11 | BD13 / BD26 | BD26 | `=AY13-AZ13` |
| BG | 2 | BG22 / BG26 | BG26 | `=AVERAGE(BG8:BG20)` |
| E | 14 | E8 / E21 | E21 | `=S22` |
| J | 1 | J26 / J26 | J26 | `=_xll.BDP("SPX INDEX","LAST PRICE")` |
| O | 15 | O8 / O24 | O24 | `=+M8/J8-1` |
| R | 4 | R22 / R26 | R26 | `=AVERAGE(R8:R19)` |
| S | 4 | S22 / S26 | S26 | `=AVERAGE(S8:S19)` |
| T | 4 | T22 / T26 | T26 | `=AVERAGE(T8:T19)` |
| W | 16 | W8 / W26 | W26 | `=1/V8` |
| Y | 4 | Y22 / Y26 | Y26 | `=AVERAGE(Y8:Y19)` |
| AA | 16 | AA8 / AA26 | AA26 | `=1/Q8` |
| AC | 16 | AC8 / AC26 | AC26 | `=+AA8-V8` |
| AE | 16 | AE8 / AE26 | AE26 | `=AA8-Y8` |
| AG | 16 | AG8 / AG26 | AG26 | `=Q8-W8` |
| AI | 16 | AI8 / AI26 | AI26 | `=T8-V8` |
| AL | 16 | AL8 / AL26 | AL26 | `=1/AK8` |
| AN | 9 | AN15 / AN26 | AN26 | `=(1/S15)-AK15` |
| AO | 16 | AO8 / AO26 | AO26 | `=Q8-AL8` |
| AQ | 4 | AQ22 / AQ26 | AQ26 | `=AVERAGE(AQ8:AQ19)` |
| AT | 4 | AT22 / AT26 | AT26 | `=AVERAGE(AT8:AT19)` |
| AV | 4 | AV22 / AV26 | AV26 | `=AVERAGE(AV8:AV19)` |
| AW | 16 | AW8 / AW26 | AW26 | `=AV8-V8` |
| BC | 1 | BC26 / BC26 | BC26 | `=BB26-(30-6)` |
| BE | 11 | BE13 / BE26 | BE26 | `=BA13-AZ13` |

Red-font hardcoded cells: 0; examples ``. All constants and full formulas are retained in the local inventory for operator review.

## S&P vs Bonds

Used range: A1:AA324. Inventory: `{"hardcoded": 1936, "formula": 2568, "dated_cells": 1605, "bloomberg": 3}`.

T:AA Bloomberg inputs; J:R cached Excel outputs. P/S yield less Baa yield and equity P/E less Baa P/E are sponsor definitions, not an equity risk premium.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| P/S yield less Baa bond yield | P/S Yield -  Baa Bond Yield | M4:M324 | J4:J324 | LineChart / left |
| Equity P/E less Baa bond P/E | Equity P/E -  Baa Bond P/E | R4:R324 | O4:O324 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| J | 321 | J4 / J324 | J324 | `=T4` |
| K | 321 | K4 / K324 | K324 | `=AA4` |
| L | 321 | L4 / L324 | L324 | `=X4` |
| M | 321 | M4 / M324 | M324 | `=(1/K4)-(L4/100)` |
| P | 321 | P4 / P324 | P324 | `=U4` |
| Q | 321 | Q4 / Q324 | Q324 | `=X4` |
| R | 321 | R4 / R324 | R324 | `=P4-(1/(Q4/100))` |
| T | 1 | T4 / T4 | T324 | `=_xll.BDH("SPX Index", "BEST_PE_RATIO", "2000-01-01", TODAY(), "BEST_FPERIOD_OVERRIDE=2FY", "per=m","cols=2;rows=321")` |
| W | 1 | W4 / W4 | W324 | `=_xll.BDH("I08221 Index", "INDEX_YIELD_TO_WORST", "2000-01-01", "", "Per=M","cols=2;rows=321")` |
| Z | 1 | Z4 / Z4 | Z324 | `=_xll.BDH("SPX Index", "px_to_sales_ratio", "2000-01-01", TODAY(), "BEST_FPERIOD_OVERRIDE=2FY", "per=m","cols=2;rows=321")` |
| O | 321 | O4 / O324 | O324 | `=T4` |

Red-font hardcoded cells: 0; examples ``. All constants and full formulas are retained in the local inventory for operator review.

## Valuation

Used range: A1:K12. Inventory: `{"hardcoded": 51, "dated_cells": 4, "formula": 16, "bloomberg": 6}`.

C:E are fixed historical benchmarks; F current Bloomberg values; H current vs 2000. Preserve benchmark dates and values.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| C | 3 | C10 / C12 | C12 | `=1/C4` |
| D | 3 | D10 / D12 | D12 | `=1/D4` |
| E | 3 | E10 / E12 | E12 | `=1/E4` |
| F | 10 | F3 / F12 | F12 | `=TODAY()` |
| H | 3 | H10 / H12 | H12 | `=F10-C10` |

Red-font hardcoded cells: 0; examples ``. All constants and full formulas are retained in the local inventory for operator review.

## S&P 500 Fundamentals

Used range: A1:AC7012. Inventory: `{"hardcoded": 14290, "bloomberg": 5, "dated_cells": 7241, "missing_cache": 2, "formula": 723}`.

B:R Bloomberg/BQL sources; W:AC sponsor calculations. L23 and Q23 have no formula cache (BQL spill anchors); downstream dated numeric results are independent saved values. Large BQL tables include identity/header rows, not observations.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| S&P 500 P/E vs Operating Margin | S&P 500 P/E | C23:C129 | B23:B129 | LineChart / left |
| S&P 500 P/E vs Operating Margin | Operating Margin | F23:F129 | E23:E129 (inferred own dates) | LineChart / right |
| S&P 500 P/E vs ROE | S&P 500 P/E | C23:C129 | B23:B129 | LineChart / left |
| S&P 500 P/E vs ROE | ROE | I23:I129 | H23:H129 (inferred own dates) | LineChart / right |
| S&P 500 Dividends & Buybacks | Dividends | X25:X129 | W25:W129 | BarChart / left |
| S&P 500 Dividends & Buybacks | Buybacks | Y25:Y129 | W25:W129 | BarChart / left |
| S&P 500 Dividends & Buybacks | Total | Z25:Z129 | W25:W129 | LineChart / left |
| Y/Y Change in Dividends & Buybacks | Div % | AA25:AA129 | W25:W129 | LineChart / left |
| Y/Y Change in Dividends & Buybacks | Buyback % | AB25:AB129 | W25:W129 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| E | 1 | E23 / E23 | E129 | `=_xll.BDH("SPX Index", "OPER_MARGIN", "2000-01-01", "2026-10-16", "PER=Q","cols=2;rows=107")` |
| H | 1 | H23 / H23 | H129 | `=_xll.BDH("SPX Index", "RETURN_COM_EQY", "2000-03-31", "2026-10-16", "PER=Q","cols=2;rows=107")` |
| L | 1 | L23 / L23 | L129 | `=_xll.BQL("members('SPX Index')", "rolling(sum(group(CF_DVD_PAID(fpt=q))), iterationdates=range(2000-12-31, btoday(), frq=q))", "currency=USD", "fill=prev","cols=2;rows=107")` |
| Q | 1 | Q23 / Q23 | Q129 | `=_xll.BQL("members('SPX Index')", "rolling(sum(group(CF_DECR_CAP_STOCK(fpt=q))), iterationdates=range(2000-12-31, btoday(), frq=q))", "currency=USD","cols=2;rows=107")` |
| X | 105 | X25 / X129 | X129 | `=-M25` |
| Y | 105 | Y25 / Y129 | Y129 | `=-R25` |
| Z | 105 | Z25 / Z129 | Z129 | `=X25+Y25` |
| AA | 101 | AA29 / AA129 | AA129 | `=X29/X25-1` |
| AB | 101 | AB29 / AB129 | AB129 | `=Y29/Y25-1` |
| AC | 101 | AC29 / AC129 | AC129 | `=Z29/Z25-1` |
| B | 1 | B23 / B23 | B6948 | `=_xll.BDH("SPX Index", "BEST_PE_RATIO", "2000-03-31", TODAY(), "BEST_FPERIOD_OVERRIDE=2FY", "per=q","cols=2;rows=107")` |
| W | 105 | W25 / W129 | W129 | `=L25` |

Red-font hardcoded cells: 0; examples ``. All constants and full formulas are retained in the local inventory for operator review.

## Margin Debt

Used range: A1:AE358. Inventory: `{"hardcoded": 1314, "formula": 2667, "dated_cells": 1275, "bloomberg": 2}`.

W:X GDP, Z:AA FINRA margin debt in millions, AC:AD Wilshire market cap in millions. FINRA data must be manually updated; market cap hardcoded through early 2026 then Bloomberg. K:U retains sponsor unit alignment/calculations. B:G peak/trough benchmarks preserved.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| Margin Debt/GDP | Margin Debt/GDP | N4:N109 | K4:K109 | LineChart / left |
| Margin Debt/GDP | Avg | O4:O109 | K4:K109 | LineChart / left |
| Margin Debt/Market Cap | Margin Debt/Market Cap | T4:T357 | Q4:Q357 | LineChart / left |
| Margin Debt/Market Cap | Avg | U4:U357 | Q4:Q357 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| W | 1 | W4 / W4 | W109 | `=_xll.BDH("GDP CUR$ Index", "PX_LAST", "2000-01-01", TODAY(),"cols=2;rows=106")` |
| K | 106 | K4 / K109 | K109 | `=W4` |
| L | 106 | L4 / L109 | L109 | `=X4` |
| M | 106 | M4 / M109 | M109 | `=VLOOKUP(K4,$Z$4:$AA$357,2,FALSE)/1000` |
| N | 106 | N4 / N109 | N109 | `=M4/L4` |
| O | 106 | O4 / O109 | O109 | `=AVERAGE($N$4:$N$1048576)` |
| R | 354 | R4 / R357 | R357 | `=AD4` |
| S | 354 | S4 / S357 | S357 | `=VLOOKUP(Q4,$Z$4:$AA$357,2,FALSE)` |
| T | 354 | T4 / T357 | T357 | `=S4/R4` |
| U | 354 | U4 / U357 | U357 | `=AVERAGE($T$4:$T$1048576)` |
| Z | 354 | Z4 / Z357 | Z357 | `=AC4` |
| AC | 1 | AC352 / AC352 | AC358 | `=_xll.BDH("W5KFLT Index", "CUR_MKT_CAP", "2024-04-25", "", "PER=M","cols=2;rows=7")` |
| F | 6 | F7 / F13 | F13 | `=D7/D6-1` |
| Q | 354 | Q4 / Q357 | Q357 | `=AC4` |
| D | 1 | D13 / D13 | D13 | `=AA357/1000` |
| G | 6 | G7 / G13 | G13 | `=D7/E6-1` |

Red-font hardcoded cells: 709; examples `AA4, AD4, AA5, AD5, AA6, AD6, AA7, AD7, AA8, AD8, AA9, AD9, AA10, AD10, AA11, AD11, AA12, AD12, AA13, AD13, AA14, AD14, AA15, AD15, AA16, AD16, AA17, AD17, AA18, AD18, AA19, AD19, AA20, AD20, AA21`. All constants and full formulas are retained in the local inventory for operator review.

## S&P Relative

Used range: A1:Y925. Inventory: `{"hardcoded": 5223, "formula": 10716, "dated_cells": 4605, "bloomberg": 323}`.

P:Q index, S:T gold, V:W WTI. WTI hardcoded through 1999, individually dated formulas thereafter; authorized operator must append next month and extend B:N calculations. Sheet explicitly says 7-year MA/difference need updating. Do not silently repair rolling windows.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| S&P 500 to Gold | Ratio | E5:E925 | B5:B925 | LineChart / left |
| S&P 500 to Gold | 7Yr MA | F5:F925 | B5:B925 | LineChart / left |
| S&P 500 to WTI | Ratio | L5:L925 | I5:I925 | LineChart / left |
| S&P 500 to WTI | 7Yr Moving Avg | M5:M925 | I5:I925 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| B | 921 | B5 / B925 | B925 | `=P5` |
| I | 921 | I5 / I925 | I925 | `=P5` |
| P | 1 | P5 / P5 | P925 | `=_xll.BDH("SPX Index", "PX_LAST", "1950-01-01", "", "Per=M","cols=2;rows=921")` |
| C | 921 | C5 / C925 | C925 | `=Q5` |
| D | 921 | D5 / D925 | D925 | `=T5` |
| E | 921 | E5 / E925 | E925 | `=C5/D5` |
| F | 837 | F89 / F925 | F925 | `=AVERAGE(E5:E89)` |
| G | 837 | G89 / G925 | G925 | `=E89-F89` |
| J | 921 | J5 / J925 | J925 | `=Q5` |
| K | 921 | K5 / K925 | K925 | `=W5` |
| L | 921 | L5 / L925 | L925 | `=J5/K5` |
| M | 837 | M89 / M925 | M925 | `=AVERAGE(L5:L89)` |
| N | 837 | N89 / N925 | N925 | `=L89-M89` |
| S | 1 | S5 / S5 | S925 | `=_xll.BDH("XAU Curncy", "PX_LAST", "1950-01-01", "", "Per=M","cols=2;rows=921")` |
| W | 321 | W605 / W925 | W925 | `=_xll.BDH("CL1 Comb Comdty", "PX_LAST", TEXT(V605, "YYYYMMDD"), TEXT(V605, "YYYYMMDD"), "days=a", "fill=p")` |

Red-font hardcoded cells: 600; examples `W5, W6, W7, W8, W9, W10, W11, W12, W13, W14, W15, W16, W17, W18, W19, W20, W21, W22, W23, W24, W25, W26, W27, W28, W29, W30, W31, W32, W33, W34, W35, W36, W37, W38, W39`. All constants and full formulas are retained in the local inventory for operator review.

## Gold to Oil

Used range: A1:Q463. Inventory: `{"hardcoded": 1854, "bloomberg": 2, "dated_cells": 1380, "formula": 2306}`.

B:F Bloomberg inputs, H:L cached ratios/long-term average; N23:Q29 implied prices and upside/downside use fixed row 463. New observations require extending formulas AND updating these fixed endpoints in Excel.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| Gold to Brent Oil | Gold/Oil | K4:K463 | H4:H463 | LineChart / left |
| Gold to Brent Oil | LT Avg. | L4:L463 | H4:H463 | LineChart / left |
| Gold to Brent Oil | Brent (C01) | J4:J463 | H4:H463 | LineChart / right |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| B | 1 | B4 / B4 | B463 | `=_xll.BDH("XAU Curncy", "PX_LAST", "1988-06-30", "", "Per=M","cols=2;rows=460")` |
| H | 460 | H4 / H463 | H463 | `=B4` |
| E | 1 | E4 / E4 | E463 | `=_xll.BDH("CO1 Comdty", "PX_LAST", "1950-01-01", "", "Per=M","cols=2;rows=460")` |
| I | 460 | I4 / I463 | I463 | `=C4` |
| J | 460 | J4 / J463 | J463 | `=F4` |
| K | 460 | K4 / K463 | K463 | `=I4/J4` |
| L | 460 | L4 / L463 | L463 | `=AVERAGE($K$4:$K$463)` |
| Q | 6 | Q23 / Q29 | Q29 | `=J463*L463` |

Red-font hardcoded cells: 0; examples ``. All constants and full formulas are retained in the local inventory for operator review.

## Bull vs Bear

Used range: A1:AA2049. Inventory: `{"hardcoded": 8321, "bloomberg": 8182, "dated_cells": 6135, "formula": 10366, "invalid": 2025}`.

B:F and N:Q Bloomberg; H:L Excel; S:T fixed decile lookup; V:AA saved conditional returns. Forward returns contain BQL capacity-error text. Unavailable values stay missing, never zero. Historical conditional returns are descriptive and overlap/publication controls are not established.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| AAII Bull - Bear | Bull - Bear | I5:I2049 | H5:H2049 | LineChart / left |
| AAII Bull - Bear | Current | L5:L2049 | H5:H2049 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| N | 2045 | N5 / N2049 | N2049 | `=_xll.BQL($N$1, "TOTAL_RETURN(CALC_INTERVAL=range(" & _xll.BQL.DATE(B5) & "," & _xll.BQL.DATE(B5) & "+1m))")` |
| B | 1 | B5 / B5 | B2049 | `=_xll.BDH("AAIIBULL Index", "PX_LAST", "1987-01-01", "", "Per=W","cols=2;rows=2045")` |
| H | 2045 | H5 / H2049 | H2049 | `=B5` |
| W | 1 | W16 / W16 | W16 | `=K2049` |
| X | 10 | X5 / X14 | X14 | `=AVERAGEIF($K$5:$K$4975,"=1",N5:N4975)` |
| E | 1 | E5 / E5 | E2049 | `=_xll.BDH("AAIIBEAR Index", "PX_LAST", "1987-01-01", "", "Per=W","cols=2;rows=2045")` |
| I | 2045 | I5 / I2049 | I2049 | `=C5-F5` |
| J | 2045 | J5 / J2049 | J2049 | `=ROUND(PERCENTRANK($I$5:$I$2665,I5)*100,0)` |
| K | 2045 | K5 / K2049 | K2049 | `=VLOOKUP(J5,$S$6:$T$106,2,FALSE)` |
| L | 2045 | L5 / L2049 | L2049 | `=$I$2049` |
| O | 2045 | O5 / O2049 | O2049 | `=_xll.BQL($N$1, "TOTAL_RETURN(CALC_INTERVAL=range(" & _xll.BQL.DATE(B5) & "," & _xll.BQL.DATE(B5) & "+3m))")` |
| P | 2045 | P5 / P2049 | P2049 | `=_xll.BQL($N$1, "TOTAL_RETURN(CALC_INTERVAL=range(" & _xll.BQL.DATE(B5) & "," & _xll.BQL.DATE(B5) & "+6m))")` |
| Q | 2045 | Q5 / Q2049 | Q2049 | `=_xll.BQL($N$1, "TOTAL_RETURN(CALC_INTERVAL=range(" & _xll.BQL.DATE(B5) & "," & _xll.BQL.DATE(B5) & "+12m))")` |
| S | 100 | S7 / S106 | S106 | `=+S6+1` |
| Y | 10 | Y5 / Y14 | Y14 | `=AVERAGEIF($K$5:$K$4975,"=1",O5:O4975)` |
| Z | 10 | Z5 / Z14 | Z14 | `=AVERAGEIF($K$5:$K$4975,"=1",P5:P4975)` |
| AA | 10 | AA5 / AA14 | AA14 | `=AVERAGEIF($K$5:$K$4975,"=1",Q5:Q4975)` |

Red-font hardcoded cells: 0; examples ``. All constants and full formulas are retained in the local inventory for operator review.

## VIX & Options

Used range: A1:L1399. Inventory: `{"hardcoded": 6428, "bloomberg": 3, "dated_cells": 3211, "formula": 3211}`.

Bloomberg series plus cached current-reference lines. Chart endpoints stop at row 1078 although sheet extends to row 1399; reproduce configured chart range, report clipping, and require mapping review to extend.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| VIX Call Options | VIX Call Options | C3:C1078 | B3:B1078 | LineChart / left |
| VIX Call Options | Current | D3:D1078 | B3:B1078 | LineChart / left |
| S&P 500 Put Volume | S&P Put Volume | G3:G1078 | F3:F1078 | LineChart / left |
| S&P 500 Put Volume | Current | H3:H1078 | F3:F1078 | LineChart / left |
| CBOE Put/Call Ratio | CBOE Put/Call Ratio | K3:K1078 | J3:J1078 | LineChart / left |
| CBOE Put/Call Ratio | Current | L3:L1078 | J3:J1078 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| B | 1 | B3 / B3 | B1078 | `=_xll.BDH("VIX Index", "VOLUME_TOTAL_CALL", "2006-01-01", "2026-10-15", "per=w","cols=2;rows=1076")` |
| D | 1076 | D3 / D1078 | D1078 | `=$C$1078` |
| F | 1 | F3 / F3 | F1078 | `=_xll.BDH("SPX Index", "VOLUME_TOTAL_PUT", "2006-03-03", "2026-10-15", "per=w","cols=2;rows=1076")` |
| H | 1076 | H3 / H1078 | H1078 | `=$G$1078` |
| J | 1 | J3 / J3 | J1061 | `=_xll.BDH("OPWVCBOR Index", "PX_LAST", "2006-03-01", "2026-10-15", "per=w","cols=2;rows=1059")` |
| L | 1059 | L3 / L1061 | L1061 | `=$K$1061` |

Red-font hardcoded cells: 0; examples ``. All constants and full formulas are retained in the local inventory for operator review.

## AAII Bull

Used range: A1:AN2047. Inventory: `{"hardcoded": 22493, "dated_cells": 10142, "formula": 14376, "bloomberg": 16224}`.

Auxiliary substantive worksheet, not a separate sponsor section. Additional Bloomberg returns and hardcoded decile lookup; mapped as an optional Bull vs Bear chart. Do not substitute it for the requested bull-minus-bear study.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| AAII Bull Index 1987-Present | AAII Bull | C20:C2047 | B20:B2047 | LineChart / left |
| AAII Bull Index 1987-Present | Current | D20:D2047 | B20:B2047 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| F | 2028 | F20 / F2047 | F2047 | `=IF(_xll.BDP($G$1,$G$2,$G$3,TEXT(B20,"YYYYMMDD"),$G$4,TEXT(N20,"YYYYMMDD"))="#N/A N/A","NA",_xll.BDP($G$1,$G$2,$G$3,TEXT(B20,"YYYYMMDD"),$G$4,TEXT(N20,"YYYYMMDD")))` |
| G | 2028 | G20 / G2047 | G2047 | `=IF(_xll.BDP($G$1,$G$2,$G$3,TEXT(B20,"YYYYMMDD"),$G$4,TEXT(O20,"YYYYMMDD"))="#N/A N/A","NA",_xll.BDP($G$1,$G$2,$G$3,TEXT(B20,"YYYYMMDD"),$G$4,TEXT(O20,"YYYYMMDD")))` |
| J | 2028 | J20 / J2047 | J2047 | `=IF(_xll.BDP($J$1,$J$2,$J$3,TEXT($B20,"YYYYMMDD"),$J$4,TEXT(N20,"YYYYMMDD"))="#N/A N/A","NA",_xll.BDP($J$1,$J$2,$J$3,TEXT($B20,"YYYYMMDD"),$J$4,TEXT(N20,"YYYYMMDD")))` |
| U | 10 | U5 / U14 | U2047 | `=AVERAGEIF($S$20:$S$5000,"=1",U20:U5000)/100` |
| Y | 10 | Y5 / Y14 | Y2047 | `=AVERAGEIF($S$20:$S$5000,"=1",Y20:Y5000)/100` |
| S | 2028 | S20 / S2047 | S2047 | `=VLOOKUP(T20,$AD$20:$AE$120,2,FALSE)` |
| V | 10 | V5 / V14 | V2047 | `=AVERAGEIF($S$20:$S$5000,"=1",V20:V5000)/100` |
| W | 10 | W5 / W14 | W2047 | `=AVERAGEIF($S$20:$S$5000,"=1",W20:W5000)/100` |
| X | 10 | X5 / X14 | X2047 | `=AVERAGEIF($S$20:$S$5000,"=1",X20:X5000)/100` |
| Z | 10 | Z5 / Z14 | Z2047 | `=AVERAGEIF($S$20:$S$5000,"=1",Z20:Z5000)/100` |
| AA | 10 | AA5 / AA14 | AA2047 | `=AVERAGEIF($S$20:$S$5000,"=1",AA20:AA5000)/100` |
| AB | 10 | AB5 / AB14 | AB2047 | `=AVERAGEIF($S$20:$S$5000,"=1",AB20:AB5000)/100` |
| N | 2028 | N20 / N2047 | N2047 | `=B20+(31*$N$18)` |
| O | 2028 | O20 / O2047 | O2047 | `=B20+(31*$O$18)` |
| P | 2028 | P20 / P2047 | P2047 | `=B20+(31*$P$18)` |
| AD | 100 | AD21 / AD120 | AD120 | `=+AD20+1` |
| D | 2028 | D20 / D2047 | D2047 | `=$C$20` |
| E | 2028 | E20 / E2047 | E2047 | `=ROUND(PERCENTRANK($C$20:$C$2047,C20)*100,0)` |
| H | 2028 | H20 / H2047 | H2047 | `=IF(_xll.BDP($G$1,$G$2,$G$3,TEXT(B20,"YYYYMMDD"),$G$4,TEXT(P20,"YYYYMMDD"))="#N/A N/A","NA",_xll.BDP($G$1,$G$2,$G$3,TEXT(B20,"YYYYMMDD"),$G$4,TEXT(P20,"YYYYMMDD")))` |
| I | 2028 | I20 / I2047 | I2047 | `=IF(_xll.BDP($G$1,$G$2,$G$3,TEXT(B20,"YYYYMMDD"),$G$4,TEXT(Q20,"YYYYMMDD"))="#N/A N/A","NA",_xll.BDP($G$1,$G$2,$G$3,TEXT(B20,"YYYYMMDD"),$G$4,TEXT(Q20,"YYYYMMDD")))` |
| K | 2028 | K20 / K2047 | K2047 | `=IF(_xll.BDP($J$1,$J$2,$J$3,TEXT($B20,"YYYYMMDD"),$J$4,TEXT(O20,"YYYYMMDD"))="#N/A N/A","NA",_xll.BDP($J$1,$J$2,$J$3,TEXT($B20,"YYYYMMDD"),$J$4,TEXT(O20,"YYYYMMDD")))` |
| L | 2028 | L20 / L2047 | L2047 | `=IF(_xll.BDP($J$1,$J$2,$J$3,TEXT($B20,"YYYYMMDD"),$J$4,TEXT(P20,"YYYYMMDD"))="#N/A N/A","NA",_xll.BDP($J$1,$J$2,$J$3,TEXT($B20,"YYYYMMDD"),$J$4,TEXT(P20,"YYYYMMDD")))` |
| M | 2028 | M20 / M2047 | M2047 | `=IF(_xll.BDP($J$1,$J$2,$J$3,TEXT($B20,"YYYYMMDD"),$J$4,TEXT(Q20,"YYYYMMDD"))="#N/A N/A","NA",_xll.BDP($J$1,$J$2,$J$3,TEXT($B20,"YYYYMMDD"),$J$4,TEXT(Q20,"YYYYMMDD")))` |
| Q | 2028 | Q20 / Q2047 | Q2047 | `=B20+365` |

Red-font hardcoded cells: 5; examples `S5, S14, N18, O18, P18`. All constants and full formulas are retained in the local inventory for operator review.

## BTC

Used range: A1:E16. Inventory: `{"hardcoded": 16, "bloomberg": 1, "formula": 7}`.

D4 Bitcoin position, D8 debt/preferred sum, D15 cost basis manually maintained from Strategy Analytics/Ledger. D5 Bloomberg BTC price; D6:D16 cached sponsor outputs; USD millions vs USD/BTC preserved.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| D | 8 | D5 / D16 | D16 | `=_xll.BDP("XBTUSD Curncy","PX_LAST")` |

Red-font hardcoded cells: 2; examples `D4, D15`. All constants and full formulas are retained in the local inventory for operator review.

## Banks

Used range: A1:F44. Inventory: `{"hardcoded": 84, "bloomberg": 1, "dated_cells": 42}`.

Bloomberg quarterly net charge-offs; population/units are from sponsor workbook, do not replace with another bank universe.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| Bank Net Charge-Offs | NCOs | C3:C44 | B3:B44 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| B | 1 | B3 / B3 | B44 | `=_xll.BDH("BISPRBAC Index", "NET_CHARGE_OFF_RATE_AVG", "2016-01-01", "", "FUND_PER=Q", "PER=Q","cols=2;rows=42")` |

Red-font hardcoded cells: 0; examples ``. All constants and full formulas are retained in the local inventory for operator review.

## Housing

Used range: A1:AG344. Inventory: `{"hardcoded": 6209, "bloomberg": 11, "dated_cells": 3099}`.

Independent date columns for different monthly/quarterly frequencies. Preserve secondary axes; never align affordability with the longer mortgage series by row position.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| Affordability & 30Yr Mortgage Rate | Affordability | C24:C129 | B24:B129 | LineChart / left |
| Affordability & 30Yr Mortgage Rate | 30Yr Mortgage | AD24:AD344 | AC24:AC344 (inferred own dates) | LineChart / right |
| Existing Home Sales, Inventory, & Months of Supply | Months of Supply | L24:L344 | K24:K344 (inferred own dates) | BarChart / left |
| Existing Home Sales, Inventory, & Months of Supply | Existing Home Sales | F24:F344 | E24:E344 | LineChart / right |
| Existing Home Sales, Inventory, & Months of Supply | Existing Home Inventory | I24:I344 | H24:H344 (inferred own dates) | LineChart / left |
| Existing home median price | Existing Home Median Price | O24:O344 | N24:N344 | LineChart / left |
| Single Family Starts & Permits | Single-Family Starts | R24:R343 | Q24:Q343 | LineChart / left |
| Single Family Starts & Permits | Single-Family Permits | U24:U343 | T24:T343 (inferred own dates) | LineChart / left |
| Purchase & Refi Applications | Purchase Applications | X24:X344 | W24:W344 | LineChart / left |
| Purchase & Refi Applications | Refi Applications | AA24:AA344 | Z24:Z344 (inferred own dates) | LineChart / right |
| Homeowners' equity | Homeowners' Equity | AG24:AG129 | AF24:AF129 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| B | 1 | B24 / B24 | B129 | `=_xll.BDH("HOMECOMP Index", "PX_LAST", "2000-01-01", "", "Per=M","cols=2;rows=106")` |
| E | 1 | E24 / E24 | E344 | `=_xll.BDH("ETSLTOTL Index", "PX_LAST", "2000-01-01", "", "PER=M","cols=2;rows=321")` |
| H | 1 | H24 / H24 | H344 | `=_xll.BDH("ETSLHAFS Index", "PX_LAST", "2000-01-01", "", "PER=M","cols=2;rows=321")` |
| K | 1 | K24 / K24 | K344 | `=_xll.BDH("ETSLMSUP Index", "PX_LAST", "2000-01-01", "", "PER=M","cols=2;rows=321")` |
| N | 1 | N24 / N24 | N344 | `=_xll.BDH("ETSLMP Index", "PX_LAST", "2000-01-01", "", "PER=M","cols=2;rows=321")` |
| Q | 1 | Q24 / Q24 | Q343 | `=_xll.BDH("NHSPS1 Index", "PX_LAST", "2000-01-01", "", "PER=M","cols=2;rows=320")` |
| T | 1 | T24 / T24 | T343 | `=_xll.BDH("NHSPA1 Index", "PX_LAST", "2000-01-01", "", "PER=M","cols=2;rows=320")` |
| W | 1 | W24 / W24 | W344 | `=_xll.BDH("MBAVPRCH Index", "PX_LAST", "2000-01-01", "", "PER=M","cols=2;rows=321")` |
| Z | 1 | Z24 / Z24 | Z344 | `=_xll.BDH("MBAVREFI Index", "PX_LAST", "2000-01-01", "", "PER=M","cols=2;rows=321")` |
| AC | 1 | AC24 / AC24 | AC344 | `=_xll.BDH("ILM3NAVG Index", "PX_LAST", "2000-01-01", "", "PER=M","cols=2;rows=321")` |
| AF | 1 | AF24 / AF24 | AF129 | `=_xll.BDH("NWOREQTY Index", "PX_LAST", "2000-01-01", "", "PER=M","cols=2;rows=106")` |

Red-font hardcoded cells: 0; examples ``. All constants and full formulas are retained in the local inventory for operator review.

## Energy

Used range: A1:AD344. Inventory: `{"hardcoded": 4048, "bloomberg": 8, "dated_cells": 2528, "formula": 1028}`.

Bloomberg source pairs B:C, E:F, H:I, N:O, Q:R, T:U, W:X, Z:AA. K:L and AC:AD are calculated efficiencies. WTI/Henry Hub use futures tickers CL1/NG1; gas Bcfd and Bcf axes differ. Chart endpoints are shorter than source columns.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| US oil production | US Oil Production | C24:C300 | B24:B300 | LineChart / left |
| US Oil Rigs vs WTI | Oil Rigs | F24:F300 | E24:E300 | BarChart / left |
| US Oil Rigs vs WTI | WTI | I24:I300 | H24:H300 (inferred own dates) | LineChart / right |
| Oil Efficiency: Production per Rig | Efficiency | L24:L300 | K24:K300 | BarChart / left |
| US Gas Production | Marcellus (Bcfd) | R24:R260 | Q24:Q260 (inferred own dates) | BarChart / left |
| US Gas Production | Haynesville (Bcfd) | U24:U260 | T24:T260 (inferred own dates) | BarChart / left |
| US Gas Production | US Gas Marketed Production (Bcf) | X24:X258 | W24:W258 | LineChart / right |
| US Gas Rigs vs Henry Hub | Gas Rigs | O24:O260 | N24:N260 | BarChart / left |
| US Gas Rigs vs Henry Hub | Henry Hub | AA24:AA260 | Z24:Z260 (inferred own dates) | LineChart / right |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| B | 1 | B24 / B24 | B300 | `=_xll.BDH(B21, "PX_LAST", "2000-01-01", "", "Per=M","cols=2;rows=277")` |
| E | 1 | E24 / E24 | E300 | `=_xll.BDH(E21, "PX_LAST", "2003-09-30", "", "Per=M","cols=2;rows=277")` |
| H | 1 | H24 / H24 | H300 | `=_xll.BDH(H21, "PX_LAST", "2003-09-30", "", "Per=M","cols=2;rows=277")` |
| N | 1 | N24 / N24 | N260 | `=_xll.BDH(N21, "PX_LAST", "2007-01-31", "", "Per=M","cols=2;rows=237")` |
| Q | 1 | Q24 / Q24 | Q260 | `=_xll.BDH(Q21, "PX_LAST", "2007-01-31", "", "Per=M","cols=2;rows=237")` |
| T | 1 | T24 / T24 | T260 | `=_xll.BDH(T21, "PX_LAST", "2007-01-31", "", "Per=M","cols=2;rows=237")` |
| W | 1 | W24 / W24 | W258 | `=_xll.BDH(W21, "PX_LAST", "2007-01-31", "", "Per=M","cols=2;rows=235")` |
| Z | 1 | Z24 / Z24 | Z260 | `=_xll.BDH(Z21, "PX_LAST", "2007-01-31", "", "Per=M","cols=2;rows=237")` |
| K | 277 | K24 / K300 | K300 | `=B24` |
| L | 277 | L24 / L300 | L300 | `=C24/F24` |
| AC | 237 | AC24 / AC260 | AC260 | `=N24` |
| AD | 237 | AD24 / AD260 | AD260 | `=X24/O24` |

Red-font hardcoded cells: 0; examples ``. All constants and full formulas are retained in the local inventory for operator review.

## Recession

Used range: A1:U808. Inventory: `{"hardcoded": 4568, "formula": 12, "bloomberg": 13, "dated_cells": 1828}`.

B/D/F/H checklist has manual text states and Bloomberg numbers; G saved flags; D55=17 denominator. F55 SUM(G8:G55) includes total row but G55 is blank. H notes govern thresholds. U Sahm warning line is hardcoded 0.5. Manual statuses are not proven current by a new save.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| Sahm Rule Recession Indicator | Series 1 | T8:T808 | S8:S808 | LineChart / left |
| Sahm Rule Recession Indicator | Series 2 | U8:U808 | S8:S808 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| J | 1 | J8 / J8 | J422 | `=_xll.BDH("DGNOYOY Index", "PX_LAST", "1950-01-01", "","cols=2;rows=415")` |
| K | 3 | K1 / K3 | K422 | `=K147` |
| M | 1 | M8 / M8 | M313 | `=_xll.BDH("GDPYFIXI Index", "PX_LAST", "1950-01-01", "","cols=2;rows=306")` |
| N | 3 | N1 / N3 | N313 | `=N313` |
| P | 1 | P8 / P8 | P313 | `=_xll.BDH("GDPYRESI Index", "PX_LAST", "1950-01-01", "","cols=2;rows=306")` |
| Q | 3 | Q1 / Q3 | Q313 | `=Q313` |
| F | 12 | F11 / F56 | F56 | `=_xll.BDP("USYC2Y10 Index","LAST_PRICE")` |
| S | 1 | S8 / S8 | S808 | `=_xll.BDH("SAHMRLRT Index", "PX_LAST", "1950-01-01", "","cols=2;rows=801")` |

Red-font hardcoded cells: 3; examples `F8, F26, F49`. All constants and full formulas are retained in the local inventory for operator review.

## Consumer

Used range: A1:I282. Inventory: `{"hardcoded": 1209, "bloomberg": 3, "dated_cells": 602}`.

Bloomberg series and source-specific units; debt-service rate and savings rate have different denominators.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| Household debt service ratio | HH Debt Service Ratio | C25:C110 | B25:B110 | LineChart / left |
| Consumer credit outstanding | Consumer Credit Outstanding | F25:F282 | E25:E282 | BarChart / left |
| Personal savings rate | US Personal Savings Rate | I25:I282 | H25:H282 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| B | 1 | B25 / B25 | B110 | `=_xll.BDH(B22, "PX_LAST", "2005-03-31", "", "Per=M","cols=2;rows=86")` |
| E | 1 | E25 / E25 | E282 | `=_xll.BDH(E22, "PX_LAST", "2005-03-31", "", "Per=M","cols=2;rows=258")` |
| H | 1 | H25 / H25 | H282 | `=_xll.BDH(H22, "PX_LAST", "2005-03-31", "", "Per=M","cols=2;rows=258")` |

Red-font hardcoded cells: 0; examples ``. All constants and full formulas are retained in the local inventory for operator review.

## Demand

Used range: A1:BL91. Inventory: `{"hardcoded": 118, "bloomberg": 1031, "dated_cells": 135, "formula": 1532}`.

Horizontal quarterly history/forward estimates; row 2 labels distinguish (Rep)/(Fwd), row 3 dates. Preserve red vertical latest-reported-quarter marker. Revenue/FCF/capex Excel calculations remain authoritative; do not describe all revenue as AI-specific.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| AMZN: Revenue vs Capex Growth (TTM) | Latest reported quarter | AA31:BL31 | AA3:BL3 | BarChart / left |
| AMZN: Revenue vs Capex Growth (TTM) | Latest reported quarter | AA32:BL32 | AA3:BL3 | BarChart / left |
| AMZN: Revenue vs Capex Growth (TTM) | Revenue | AA28:BL28 | AA3:BL3 | LineChart / left |
| AMZN: Revenue vs Capex Growth (TTM) | AWS | AA29:BL29 | AA3:BL3 | LineChart / left |
| AMZN: Revenue vs Capex Growth (TTM) | Capex + R&D | AA30:BL30 | AA3:BL3 | LineChart / left |
| AMZN: FCF Margin (TTM) | Latest reported quarter | AA23:BL23 | AA3:BL3 | BarChart / left |
| AMZN: FCF Margin (TTM) | Latest reported quarter | AA24:BL24 | AA3:BL3 | BarChart / left |
| AMZN: FCF Margin (TTM) |    Free Cash Flow Margin (%) | AA22:BL22 | AA3:BL3 | LineChart / left |
| GOOGL: Revenue vs Capex Growth (TTM) | Latest reported quarter | AA63:BL63 | AA3:BL3 | BarChart / left |
| GOOGL: Revenue vs Capex Growth (TTM) | Latest reported quarter | AA64:BL64 | AA3:BL3 | BarChart / left |
| GOOGL: Revenue vs Capex Growth (TTM) | Revenue | AA60:BL60 | AA3:BL3 | LineChart / left |
| GOOGL: Revenue vs Capex Growth (TTM) | Cloud | AA61:BL61 | AA3:BL3 | LineChart / left |
| GOOGL: Revenue vs Capex Growth (TTM) | Capex + R&D | AA62:BL62 | AA3:BL3 | LineChart / left |
| GOOGL: FCF Margin (TTM) | Latest reported quarter | AA55:BL55 | AA3:BL3 | BarChart / left |
| GOOGL: FCF Margin (TTM) | Latest reported quarter | AA56:BL56 | AA3:BL3 | BarChart / left |
| GOOGL: FCF Margin (TTM) |    Free Cash Flow Margin (%) | AA54:BL54 | AA3:BL3 | LineChart / left |
| META: Revenue vs Capex Growth (TTM) | Latest reported quarter | AA90:BL90 | AA3:BL3 | BarChart / left |
| META: Revenue vs Capex Growth (TTM) | Latest reported quarter | AA91:BL91 | AA3:BL3 | BarChart / left |
| META: Revenue vs Capex Growth (TTM) | Revenue | AA88:BL88 | AA3:BL3 | LineChart / left |
| META: Revenue vs Capex Growth (TTM) | Capex + R&D | AA89:BL89 | AA3:BL3 | LineChart / left |
| META: FCF Margin (TTM) | Latest reported quarter | AA83:BL83 | AA3:BL3 | BarChart / left |
| META: FCF Margin (TTM) | Latest reported quarter | AA84:BL84 | AA3:BL3 | BarChart / left |
| META: FCF Margin (TTM) |    Free Cash Flow Margin (%) | AA82:BL82 | AA3:BL3 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| T | 28 | T2 / T85 | T85 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-34Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| U | 28 | U2 / U85 | U85 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-33Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| V | 28 | V2 / V85 | V85 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-32Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| W | 50 | W2 / W86 | W86 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-31Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| X | 51 | X2 / X86 | X86 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-30Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| Y | 51 | Y2 / Y86 | Y86 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-29Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| Z | 51 | Z2 / Z86 | Z86 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-28Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AA | 59 | AA2 / AA89 | AA89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-27Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AB | 59 | AB2 / AB89 | AB89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-26Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AC | 59 | AC2 / AC89 | AC89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-25Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AD | 59 | AD2 / AD89 | AD89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-24Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AE | 60 | AE2 / AE89 | AE89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-23Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AF | 60 | AF2 / AF89 | AF89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-22Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AG | 60 | AG2 / AG89 | AG89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-21Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AH | 60 | AH2 / AH89 | AH89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-20Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AI | 60 | AI2 / AI89 | AI89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-19Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AJ | 60 | AJ2 / AJ89 | AJ89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-18Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AK | 60 | AK2 / AK89 | AK89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-17Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AL | 60 | AL2 / AL89 | AL89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-16Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AM | 60 | AM2 / AM89 | AM89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-15Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AN | 60 | AN2 / AN89 | AN89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-14Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AO | 60 | AO2 / AO89 | AO89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-13Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AP | 60 | AP2 / AP89 | AP89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-12Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AQ | 60 | AQ2 / AQ89 | AQ89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-11Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AR | 60 | AR2 / AR89 | AR89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-10Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AS | 60 | AS2 / AS89 | AS89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-9Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AT | 60 | AT2 / AT89 | AT89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-8Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AU | 60 | AU2 / AU89 | AU89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-7Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AV | 60 | AV2 / AV89 | AV89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-6Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AW | 60 | AW2 / AW89 | AW89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-5Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AX | 60 | AX2 / AX89 | AX89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-4Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AY | 60 | AY2 / AY89 | AY89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-3Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AZ | 60 | AZ2 / AZ89 | AZ89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-2Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BA | 60 | BA2 / BA89 | BA89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-1Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BB | 60 | BB2 / BB89 | BB91 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=0Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BC | 60 | BC2 / BC89 | BC89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=1Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BD | 60 | BD2 / BD89 | BD89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=2Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BE | 60 | BE2 / BE89 | BE89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=3Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BF | 60 | BF2 / BF89 | BF89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=4Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BG | 60 | BG2 / BG89 | BG89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=5Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BH | 60 | BH2 / BH89 | BH89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=6Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BI | 60 | BI2 / BI89 | BI89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=7Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BJ | 60 | BJ2 / BJ89 | BJ89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=8Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BK | 60 | BK2 / BK89 | BK89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=9Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BL | 60 | BL2 / BL89 | BL89 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=10Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |

Red-font hardcoded cells: 12; examples `BB23, BB24, BB31, BB32, BB55, BB56, BB63, BB64, BB83, BB84, BB90, BB91`. All constants and full formulas are retained in the local inventory for operator review.

## Financing

Used range: A1:BL344. Inventory: `{"hardcoded": 1331, "bloomberg": 95, "dated_cells": 976, "formula": 1122}`.

Sponsor Financing section is additional to existing Forecasting. Horizontal hyperscaler ratios and combined quarterly cash flows, plus credit/relative-performance histories. Forward estimates must be distinguished from reported quarters.

### Charts and source ranges

| Chart | Metric | Saved values | Dates | Type / axis |
|---|---|---|---|---|
| Hyperscaler Capex/CFOps (TTM) | Latest reported quarter | W8:BL8 | W3:BL3 | BarChart / left |
| Hyperscaler Capex/CFOps (TTM) | Latest reported quarter | W9:BL9 | W3:BL3 | BarChart / left |
| Hyperscaler Capex/CFOps (TTM) | AMZN | W4:BL4 | W3:BL3 | LineChart / left |
| Hyperscaler Capex/CFOps (TTM) | GOOGL | W5:BL5 | W3:BL3 | LineChart / left |
| Hyperscaler Capex/CFOps (TTM) | META | W6:BL6 | W3:BL3 | LineChart / left |
| Hyperscaler Capex/CFOps (TTM) | Combined | W7:BL7 | W3:BL3 | LineChart / left |
| Combined Capex  vs CFOps (Quarterly) | Combined Capex | W10:BL10 | W3:BL3 | BarChart / left |
| Combined Capex  vs CFOps (Quarterly) | Latest reported quarter | W12:BL12 | W3:BL3 | BarChart / left |
| Combined Capex  vs CFOps (Quarterly) | Latest reported quarter | W13:BL13 | W3:BL3 | BarChart / left |
| Combined Capex  vs CFOps (Quarterly) | Combined CFOps | W11:BL11 | W3:BL3 | LineChart / left |
| HY Tech vs IG Index | Spread | P31:P315 | O31:O315 | LineChart / left |
| HY Tech vs IG Index | Avg | Q31:Q315 | O31:O315 | LineChart / left |
| ORCL & CRWV Relative Performance to S&P 500 | ORCL RS | AC31:AC49 | AB31:AB49 | LineChart / left |
| ORCL & CRWV Relative Performance to S&P 500 | CRWV RS | AD31:AD49 | AB31:AB49 | LineChart / left |

### Formula and manual-extension inventory by column

Last formula vs last nonempty row exposes gaps and fixed endpoints; this is a review aid, not an instruction to fill cells.

| Column | Formula count | First / last formula | Last nonempty | Example formula |
|---|---:|---|---:|---|
| P | 285 | P31 / P315 | P315 | `=J31-M31` |
| T | 2 | T2 / T3 | T49 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-34Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| U | 2 | U2 / U3 | U3 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-33Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| V | 3 | V2 / V31 | V49 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-32Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| W | 7 | W2 / W11 | W49 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-31Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| X | 7 | X2 / X11 | X11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-30Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| Y | 8 | Y2 / Y31 | Y49 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-29Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| Z | 7 | Z2 / Z11 | Z49 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-28Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AA | 7 | AA2 / AA11 | AA11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-27Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AB | 26 | AB2 / AB49 | AB49 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-26Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AC | 26 | AC2 / AC49 | AC49 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-25Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AD | 26 | AD2 / AD49 | AD49 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-24Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AE | 7 | AE2 / AE11 | AE11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-23Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AF | 7 | AF2 / AF11 | AF11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-22Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AG | 7 | AG2 / AG11 | AG11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-21Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AH | 7 | AH2 / AH11 | AH11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-20Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AI | 7 | AI2 / AI11 | AI11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-19Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AJ | 7 | AJ2 / AJ11 | AJ11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-18Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AK | 7 | AK2 / AK11 | AK11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-17Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AL | 7 | AL2 / AL11 | AL11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-16Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AM | 7 | AM2 / AM11 | AM11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-15Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AN | 7 | AN2 / AN11 | AN11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-14Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AO | 7 | AO2 / AO11 | AO11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-13Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AP | 7 | AP2 / AP11 | AP11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-12Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AQ | 7 | AQ2 / AQ11 | AQ11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-11Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AR | 7 | AR2 / AR11 | AR11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-10Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AS | 7 | AS2 / AS11 | AS11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-9Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AT | 7 | AT2 / AT11 | AT11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-8Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AU | 7 | AU2 / AU11 | AU11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-7Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AV | 7 | AV2 / AV11 | AV11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-6Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AW | 7 | AW2 / AW11 | AW11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-5Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AX | 7 | AX2 / AX11 | AX11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-4Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AY | 7 | AY2 / AY11 | AY11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-3Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| AZ | 7 | AZ2 / AZ11 | AZ11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-2Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BA | 7 | BA2 / BA11 | BA11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=-1Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BB | 7 | BB2 / BB11 | BB13 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=0Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BC | 7 | BC2 / BC11 | BC11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=1Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BD | 7 | BD2 / BD11 | BD11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=2Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BE | 7 | BE2 / BE11 | BE11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=3Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BF | 7 | BF2 / BF11 | BF11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=4Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BG | 7 | BG2 / BG11 | BG11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=5Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BH | 7 | BH2 / BH11 | BH11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=6Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BI | 7 | BI2 / BI11 | BI11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=7Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BJ | 7 | BJ2 / BJ11 | BJ11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=8Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BK | 7 | BK2 / BK11 | BK11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=9Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| BL | 7 | BL2 / BL11 | BL11 | `=_xll.BQL("AMZN US Equity", "FISCAL_PERIOD", "FPT=Q", "FPO=10Q", "ACT_EST_MAPPING=PRECISE", "FS=MRC", "CURRENCY=USD", "XLFILL=b")` |
| Q | 285 | Q31 / Q315 | Q315 | `=AVERAGE($P$31:$P$500)` |
| S | 1 | S31 / S31 | S49 | `=_xll.BDH("SPX Index", "PX_LAST", "2025-03-01", "", "Per=M","cols=2;rows=19")` |
| I | 1 | I31 / I31 | I315 | `=_xll.BDH("I00465 Index", "INDEX_OAS_TSY", "2003-01-01", "", "Per=M","cols=2;rows=285")` |
| L | 1 | L31 / L31 | L315 | `=_xll.BDH("I00394US Index", "INDEX_OAS_TSY", "2003-01-01", "", "Per=M","cols=2;rows=285")` |
| O | 285 | O31 / O315 | O315 | `=I31` |

Red-font hardcoded cells: 46; examples `W7, X7, Y7, Z7, AA7, AB7, AC7, AD7, AE7, AF7, AG7, AH7, AI7, AJ7, AK7, AL7, AM7, AN7, AO7, AP7, AQ7, AR7, AS7, AT7, AU7, AV7, AW7, AX7, AY7, AZ7, BA7, BB7, BC7, BD7, BE7`. All constants and full formulas are retained in the local inventory for operator review.

## Supply and independent-source plan

No workbook worksheet exists for Supply. Show unavailable coverage explicitly. Candidate capacity/vacancy: company filings and operator disclosures (keep live vs construction, geography, MW and measurement dates separate). GPU rental: provider-published rate cards/APIs with model, region, VRAM, availability, hourly price, currency and on-demand/spot/contract terms; do not combine these contracts into one price. Bottlenecks: dated utility/interconnection and manufacturer disclosures. No verified connector or permission to scrape is implied. SEC facts can supplement filed capex/CFO; EIA can supplement energy; FRED can supply productivity. Each requires a separate verified connector and attribution before use. No synthetic observations.

## Visual acceptance and limitations

Word contains 31 chart/table illustrations, reviewed locally. Plum primary series, teal comparison, secondary axes, bar/line combinations, horizontal company grids, and last-reported-quarter red markers are mapped into interactive Plotly charts. Pixel-identical Excel rendering is not claimed. Original chart endpoints and cached calculation semantics are preserved. Some chart titles are blank in Excel; metadata supplies descriptive titles. Conditional formatting rules/checklist operator judgments are not recalculated. Formula extensions, Bloomberg freshness and independent Supply data remain operator/external dependencies.
