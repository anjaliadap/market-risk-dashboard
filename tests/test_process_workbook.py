"""Only synthetic workbook inputs; no company or licensed observation fixtures."""

import copy
import hashlib
import statistics
from calendar import monthrange
from datetime import datetime
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from openpyxl import Workbook

from src.providers.process_workbook import (
    ProcessWorkbookProvider,
    validate_process_continuity,
)

SECTORS = [
    "Consumer Durables",
    "Capital Equipment",
    "Industrial Commodities",
    "Software",
    "Hardware",
    "Pharma & Biotech",
    "Equipment & Services",
    "Retail, Media & Consumer Services",
    "Financials",
    "Consumer Staples",
    "Utilities",
    "Energy",
    "REITs",
]


def month_at(index):
    year, month = divmod(2025 * 12 + index, 12)
    return datetime(year, month + 1, 1)


def synthetic_workbook(mutate=None, months=13, q23_cache=999):
    """Mirror the supplied layout using invented readings and prices."""
    book = Workbook()
    gold = book.active
    gold.title = "Gold to Oil"
    for cell, value in {
        "B3": "Date",
        "C3": "Gold",
        "E3": "Date",
        "F3": "Brent",
        "I3": "Gold",
        "J3": "Brent (C01)",
        "K3": "Gold/Oil",
        "L3": "LT Avg.",
        "N23": "Implied Gold Price at LT Average",
        "N24": "Gold Spot",
        "N25": "Downside",
        "N27": "Implied Oil Price at LT Average",
        "N28": "Oil Spot",
        "N29": "Upside",
    }.items():
        gold[cell] = value
    ratios = []
    for i in range(months + 1):
        row = 4 + i
        date = month_at(i)
        date = date.replace(day=15 if i == months else monthrange(date.year, date.month)[1])
        price, oil = 1800 + 20 * i, 60 + i
        for col in ["B", "E", "H"]:
            gold[f"{col}{row}"] = date
        for col in ["C", "I"]:
            gold[f"{col}{row}"] = price
        for col in ["F", "J"]:
            gold[f"{col}{row}"] = oil
        ratio = price / oil
        gold[f"K{row}"] = ratio
        gold[f"K{row}"].number_format = '0.0"x"'
        ratios.append(ratio)
        if i == months:
            gold[f"A{row}"] = "Current"
        elif i == months - 1:
            gold[f"A{row}"] = "Historical"
    average = statistics.mean(ratios)
    for row in range(4, 5 + months):
        gold[f"L{row}"] = "=AVERAGE($K$4:$K$5000)"
        gold[f"L{row}"].number_format = '0.0"x"'
    current_gold, current_oil = 1800 + 20 * months, 60 + months
    for cell, value in {
        "A1": gold[f"H{4 + months}"].value,
        "X7": current_oil,
        "X8": average,
        "X9": current_oil * average,
        "X10": current_gold,
        "X11": current_oil * average / current_gold - 1,
        "X14": current_gold,
        "X15": average,
        "X16": current_gold / average,
        "X17": current_oil,
        "X18": current_gold / average / current_oil - 1,
    }.items():
        gold[cell] = value
    # Deliberate stale display results test the exact defect found in the upload.
    gold["Q23"] = "=X9-X9"
    gold["Q24"] = current_gold
    gold["Q25"] = -0.9
    gold["Q27"] = current_gold / average
    gold["Q28"] = 999
    gold["Q29"] = 999

    intra = book.create_sheet("Intra-Sector Spreads")
    intra["F1"] = "Empirical: Intra-Sector Spreads"
    intra["F3"] = "Intra-Sector Spreads"
    for row, sector in enumerate(SECTORS, 4):
        intra[f"F{row}"] = sector
    for i in range(months):
        col = 8 + i
        intra.cell(3, col, month_at(i))
        for offset in range(13):
            intra.cell(4 + offset, col, 15 + 4 * offset + i)
        values = [intra.cell(row, col).value for row in range(4, 17)]
        intra.cell(18, col, 13)
        intra.cell(19, col, sum(v > 50 for v in values))
        intra.cell(20, col, sum(v > 50 for v in values) / 13)
        intra.cell(21, col, sum(v < 50 for v in values))
        intra.cell(22, col, sum(v < 50 for v in values) / 13)
    intra.column_dimensions["H"].hidden = True
    intra["BP3"] = "Average"
    for row in range(4, 17):
        intra[f"BP{row}"] = 50

    trend = book.create_sheet("Trend-Following")
    trend["D1"] = "Empirical: Trend-Following Indicator"
    trend["D3"] = "Trend-Following Indicator"
    trend["D4"] = "Year"
    trend["D5"] = "Trend-Following Regime"
    for i in range(months):
        date = month_at(i)
        trend.cell(3, 5 + i, date.year * 100 + date.month)
        trend.cell(4, 5 + i, date.year % 100)
        trend.cell(5, 5 + i, i % 5 + 1)

    ndr = book.create_sheet("NDR")
    for cell, value in {
        "B1": "NDR",
        "B3": "Model Name",
        "C3": "Reading",
        "D3": "% Gain p.a.",
        "E3": "Since",
        "G3": "Code",
        "H3": "Notes",
        "B4": "Equities",
        "B12": "% of Indicators Flashing",
        "D12": "Prior",
        "E12": "Current",
        "B17": "Sentiment",
        "B18": "Equities",
        "B23": "Commodities",
        "B30": "Credit",
        "J4": "S&P Record Highs Calculator",
        "J5": "S&P 500 YE25",
        "J6": "% Gain",
        "J7": "Implied YE26 Price",
        "J8": "Current Price",
        "J9": "Implied Upside to YE26",
        "J11": "Next Year's Median Gain",
        "J12": "Implied YE27 Price",
        "J13": "Implied Upside to YE27",
        "J14": "   Annualized",
    }.items():
        ndr[cell] = value
    model_rows = {
        5: "S&P 500 vs Modified Federal Reserve Valuation Model",
        6: "S&P 500 vs NDR Federal Reserve Valuation Model",
        7: "S&P 500 vs US OFR Financial Stress Index",
        9: "S&P 500 vs Record Highs per Year",
        10: "   Next Year's Median Gain",
        19: "Sentiment Composite: Crowd Sentiment Poll & Daily Trading Sentiment Composite",
        20: "Sentiment Composite Adjusted for OFR Financial Stress Index",
        21: "AAII Bull Less Bear - PCM Internal",
        24: "Commodity Index vs NDR Daily Commodity Sentiment Composite",
        25: "NDR Daily Commodity Sentiment Adjusted for OFR Financial Stress Index",
        27: "West Texas Spot vs NDR Crown Sentiment Poll for Crude Futures",
        28: "NDR Crowd Sentiment for Crude Oil Adjusted for OFR Financial Stress Index",
        31: "Corporate Credit Trends (HY Performance)",
    }
    for row, model in model_rows.items():
        ndr[f"B{row}"] = model
        ndr[f"C{row}"] = None if row in [10, 21] else "Neutral"
        ndr[f"D{row}"] = 0.01 if row != 9 else 0.1
        ndr[f"E{row}"] = 1990
        ndr[f"G{row}"] = f"SYNTHETIC-{row}"
    for row, label, previous, current in [
        (13, "Global Top Watch Report (Bearish >50%)", 0.3, 0.5),
        (14, "Global Cyclical Bear Watch (Bearish >40%)", 0.2, 0.41),
        (15, "Secular Bear Watch Report (Bearish >50%)", 0.1, 0.2),
    ]:
        ndr[f"B{row}"] = label
        ndr[f"D{row}"] = previous
        ndr[f"E{row}"] = current
    target = datetime(2027, 12, 31)
    calc_date = datetime(2026, 1, 15)
    price26, spot = 5500, 5200
    price27 = price26 * 1.01
    for cell, value in {
        "K5": 5000,
        "K6": 0.1,
        "K7": price26,
        "K8": spot,
        "K9": price26 / spot - 1,
        "K11": 0.01,
        "K12": price27,
        "K13": price27 / spot - 1,
        "K14": (price27 / spot) ** (365.25 / (target - calc_date).days) - 1,
        "L12": calc_date,
        "L13": target,
        "L14": (target - calc_date).days,
    }.items():
        ndr[cell] = value
    if mutate:
        mutate(book)
    stream = BytesIO()
    book.save(stream)
    # Install an explicitly stale saved formula result without calculating Excel.
    out = BytesIO()
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(stream) as source, ZipFile(out, "w") as destination:
        for item in source.infolist():
            blob = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                root = ET.fromstring(blob)
                cell = root.find(".//m:c[@r='Q23']", ns)
                cell.find("m:v", ns).text = str(
                    current_oil * average if q23_cache == "implied" else q23_cache
                )
                for row in range(4, 5 + months):
                    cell = root.find(f".//m:c[@r='L{row}']", ns)
                    cell.find("m:v", ns).text = str(average)
                blob = ET.tostring(root)
            destination.writestr(item, blob)
    return out.getvalue()


def read_snapshot(tmp_path, **kwargs):
    blob = synthetic_workbook(**kwargs)
    path = tmp_path / "synthetic.xlsx"
    path.write_bytes(blob)
    result = ProcessWorkbookProvider(path).read()
    assert path.read_bytes() == blob
    assert result["sha256"] == hashlib.sha256(blob).hexdigest()
    return result


def test_four_sections_use_only_new_workbook_inputs(tmp_path):
    result = read_snapshot(tmp_path)
    assert set(result["sections"]) == {
        "Gold to Oil",
        "Intra-Sector Spread",
        "Trend Following",
        "NDR",
    }
    assert result["mapping_sha256"]
    assert result["latest_observation"]
    assert result["sections"]["NDR"]["as_of"] is None


def test_gold_ratios_and_implied_values_recomputed_from_matched_prices(tmp_path):
    result = read_snapshot(tmp_path)
    gold = result["sections"]["Gold to Oil"]
    current = gold["current"]
    assert current["date"] == "2026-02-15"
    assert current["gold"] == 2060
    assert current["oil"] == 73
    assert current["ratio"] == pytest.approx(2060 / 73)
    assert len(gold["history"]) == 14
    assert sum(p["is_current"] for p in gold["history"]) == 1
    assert current["average"] == pytest.approx(
        statistics.mean((1800 + 20 * i) / (60 + i) for i in range(14))
    )
    implied = {row["asset"]: row for row in gold["implied"]}
    assert implied["Gold"]["implied"] == pytest.approx(73 * current["average"])
    assert implied["Gold"]["change"] == pytest.approx(implied["Gold"]["implied"] / 2060 - 1)
    assert implied["Brent futures"]["implied"] == pytest.approx(2060 / current["average"])
    assert any(issue["cell"] in ["Q23", "Q28", "Q29"] for issue in result["issues"])


def test_gold_self_subtraction_formula_flagged_even_when_cache_looks_correct(tmp_path):
    result = read_snapshot(tmp_path, q23_cache="implied")
    gold = result["sections"]["Gold to Oil"]
    assert gold["implied"][0]["implied"] == pytest.approx(
        gold["current"]["oil"] * gold["current"]["average"]
    )
    assert any(
        issue["cell"] == "Q23" and "subtracts" in issue["reason"] for issue in result["issues"]
    )


def test_intra_dates_hidden_history_and_point_deltas(tmp_path):
    intra = read_snapshot(tmp_path)["sections"]["Intra-Sector Spread"]
    assert intra["as_of"] == "2026-01-01"
    assert len(intra["current"]) == 13
    assert len(intra["dates"]) == 13
    assert intra["dates"][0] == "2025-01-01"  # Hidden column is still an observation.
    first = next(row for row in intra["current"] if row["sector"] == SECTORS[0])
    assert first["percentile"] == 27
    assert first["average"] == 50
    assert [first[f"change_{n}m"] for n in [1, 3, 6, 12]] == [1, 3, 6, 12]


def test_intra_blank_historical_month_is_not_filled(tmp_path):
    def remove_month(book):
        for row in range(4, 23):
            book["Intra-Sector Spreads"].cell(row, 17).value = None

    intra = read_snapshot(tmp_path, mutate=remove_month)["sections"]["Intra-Sector Spread"]
    missing = [r for r in intra["history"] if r["date"] == "2025-10-01"]
    assert not missing or all(row["percentile"] is None for row in missing)
    assert all(row["change_3m"] is None for row in intra["current"])


def test_trend_yyyymm_dates_and_calendar_changes(tmp_path):
    trend = read_snapshot(tmp_path)["sections"]["Trend Following"]
    assert trend["history"][0]["date"] == "2025-01-01"
    expected = {
        "date": "2026-01-01",
        "quintile": 3,
        "change_1m": 1,
        "change_3m": -2,
        "change_6m": 1,
        "change_12m": 2,
    }
    assert {key: trend["current"][key] for key in expected} == expected


def test_dynamic_appended_months_extend_both_horizontal_histories(tmp_path):
    result = read_snapshot(tmp_path, months=14)
    assert result["sections"]["Intra-Sector Spread"]["as_of"] == "2026-02-01"
    assert result["sections"]["Trend Following"]["current"]["date"] == "2026-02-01"
    assert len(result["sections"]["Trend Following"]["history"]) == 14


@pytest.mark.parametrize("sheet,cell", [("Trend-Following", "F3"), ("Intra-Sector Spreads", "I3")])
def test_internal_missing_date_header_cannot_silently_truncate_history(tmp_path, sheet, cell):
    def remove_header(book):
        book[sheet][cell] = None

    with pytest.raises(ValueError, match="(?i)(date|month|gap|header)"):
        read_snapshot(tmp_path, mutate=remove_header)


def test_missing_trend_score_is_a_gap_and_does_not_shift_change_endpoint(tmp_path):
    def remove_score(book):
        book["Trend-Following"]["P5"] = None

    trend = read_snapshot(tmp_path, mutate=remove_score)["sections"]["Trend Following"]
    assert len(trend["history"]) == 13
    assert trend["history"][-2]["quintile"] is None
    assert trend["current"]["quintile"] == 3
    assert trend["current"]["change_1m"] is None
    assert trend["current"]["change_3m"] == -2


def test_absent_trend_calendar_month_gets_null_without_carrying_previous_regime(tmp_path):
    def remove_december(book):
        book["Trend-Following"].delete_cols(16)  # December 2025, before January 2026.

    trend = read_snapshot(tmp_path, mutate=remove_december)["sections"]["Trend Following"]
    assert len(trend["history"]) == 13
    december = next(row for row in trend["history"] if row["date"] == "2025-12-01")
    assert december["quintile"] is None
    assert trend["current"]["date"] == "2026-01-01"
    assert trend["current"]["quintile"] == 3
    assert trend["current"]["change_1m"] is None


def test_gold_mismatched_source_dates_rejected(tmp_path):
    def wrong_date(book):
        book["Gold to Oil"]["E4"] = datetime(2025, 2, 1)

    with pytest.raises(ValueError, match="(?i)dates do not match"):
        read_snapshot(tmp_path, mutate=wrong_date)


def test_gold_missing_input_cache_does_not_use_stale_ratio_or_average(tmp_path):
    def missing_cache(book):
        book["Gold to Oil"]["C4"] = '=BDP("SYNTHETIC", "PX_LAST")'

    result = read_snapshot(tmp_path, mutate=missing_cache)
    gold = result["sections"]["Gold to Oil"]
    assert gold["history"][0]["gold"] is None
    assert gold["history"][0]["ratio"] is None
    assert gold["current"]["average"] is None
    assert all(row["implied"] is None and row["change"] is None for row in gold["implied"])
    assert any(
        issue["cell"] == "C4" and "saved" in issue["reason"].lower() for issue in result["issues"]
    )


@pytest.mark.parametrize(
    "sheet,date_row,date_col", [("Trend-Following", 3, 6), ("Intra-Sector Spreads", 3, 9)]
)
def test_duplicate_months_rejected(tmp_path, sheet, date_row, date_col):
    def duplicate(book):
        book[sheet].cell(date_row, date_col).value = book[sheet].cell(date_row, date_col - 1).value

    with pytest.raises(ValueError, match="(?i)duplicate"):
        read_snapshot(tmp_path, mutate=duplicate)


@pytest.mark.parametrize("score", [0, 6, 2.5, "#N/A", True])
def test_invalid_latest_trend_quintile_stays_unavailable(tmp_path, score):
    def bad_score(book):
        book["Trend-Following"]["Q5"] = score

    result = read_snapshot(tmp_path, mutate=bad_score)
    current = result["sections"]["Trend Following"]["current"]
    assert current["quintile"] is None
    assert all(current[f"change_{m}m"] is None for m in [1, 3, 6, 12])
    assert any(
        issue["sheet"] == "Trend-Following" and issue["cell"] == "Q5" for issue in result["issues"]
    )


def test_continuity_rejects_invalid_new_current_trend_score(tmp_path):
    previous = read_snapshot(tmp_path)

    def invalid_score(book):
        book["Trend-Following"]["Q5"] = 6

    current = read_snapshot(tmp_path, mutate=invalid_score)
    with pytest.raises(ValueError):
        validate_process_continuity(previous, current)


def test_ndr_percentages_years_and_strict_thresholds(tmp_path):
    ndr = read_snapshot(tmp_path)["sections"]["NDR"]
    assert [row["triggered"] for row in ndr["warnings"]] == [False, True, False]
    assert ndr["warnings"][0]["current"] == ndr["warnings"][0]["threshold"] == 0.5
    models = [row for group in ndr["groups"] for row in group["rows"]]
    assert all(row["start_year"] == 1990 for row in models)
    assert (
        next(row for row in models if "Record Highs per Year" in row["model"])["annualized_return"]
        == 0.1
    )
    assert next(row for row in models if "PCM Internal" in row["model"])["reading"] is None


def test_ndr_scenario_uses_compounding_and_actual_calendar_days(tmp_path):
    reference, target = datetime(2024, 2, 29), datetime(2027, 12, 31)

    def stale_calculator(book):
        sheet = book["NDR"]
        sheet["L12"] = reference
        sheet["L13"] = target
        sheet["L14"] = 365  # Deliberate stale day-count cache.
        sheet["K7"] = 1  # Deliberate stale output caches must not feed the scenario.
        sheet["K12"] = 1
        sheet["K14"] = 0.99

    result = read_snapshot(tmp_path, mutate=stale_calculator)
    ndr = result["sections"]["NDR"]
    calculator = ndr["calculator"]
    rows = {row["label"].strip(): row["value"] for row in calculator["rows"]}
    assert ndr["as_of"] is None
    assert calculator["reference_date"] == "2024-02-29"
    assert calculator["target_date"] == "2027-12-31"
    assert rows["Implied YE26 Price"] == 5500
    assert rows["Implied YE27 Price"] == 5555
    assert rows["Implied Upside to YE26"] == pytest.approx(5500 / 5200 - 1)
    assert rows["Implied Upside to YE27"] == pytest.approx(5555 / 5200 - 1)
    assert rows["Annualized"] == pytest.approx(
        (5555 / 5200) ** (365.25 / (target - reference).days) - 1
    )
    assert {"K7", "K12", "K14", "L14"}.issubset(
        {issue["cell"] for issue in result["issues"] if issue["sheet"] == "NDR"}
    )


@pytest.mark.parametrize("reference", [datetime(2027, 12, 31), datetime(2028, 1, 1)])
def test_ndr_expired_scenario_has_no_annualized_return(tmp_path, reference):
    def expired_scenario(book):
        book["NDR"]["L12"] = reference

    calculator = read_snapshot(tmp_path, mutate=expired_scenario)["sections"]["NDR"]["calculator"]
    annualized = next(
        row["value"] for row in calculator["rows"] if row["label"].strip() == "Annualized"
    )
    assert annualized is None


def test_continuity_rejects_missing_previously_valid_calculator_input(tmp_path):
    previous = read_snapshot(tmp_path)

    def missing_price(book):
        book["NDR"]["K8"] = None

    current = read_snapshot(tmp_path, mutate=missing_price)
    calculator = current["sections"]["NDR"]["calculator"]
    assert (
        next(row["value"] for row in calculator["rows"] if row["label"] == "Current Price") is None
    )
    with pytest.raises(ValueError):
        validate_process_continuity(previous, current)


def test_continuity_rejects_lost_valid_historical_record(tmp_path):
    previous = read_snapshot(tmp_path)
    current = copy.deepcopy(previous)
    current["sections"]["Trend Following"]["history"].pop(0)
    with pytest.raises(ValueError):
        validate_process_continuity(previous, current)


def test_continuity_rejects_lost_valid_value_but_allows_revision(tmp_path):
    previous = read_snapshot(tmp_path)
    current = copy.deepcopy(previous)
    current["sections"]["Intra-Sector Spread"]["current"][0]["percentile"] = None
    with pytest.raises(ValueError):
        validate_process_continuity(previous, current)
    current = copy.deepcopy(previous)
    current["sections"]["Trend Following"]["history"][0]["quintile"] = 2
    validate_process_continuity(previous, current)


def test_continuity_allows_current_gold_observation_to_roll_forward(tmp_path):
    previous = read_snapshot(tmp_path)
    current = copy.deepcopy(previous)
    gold = current["sections"]["Gold to Oil"]
    gold["history"] = [row for row in gold["history"] if not row["is_current"]]
    next_current = {**gold["current"], "date": "2026-02-16", "is_current": True}
    gold["history"].append(next_current)
    gold["current"]["date"] = "2026-02-16"
    validate_process_continuity(previous, current)
