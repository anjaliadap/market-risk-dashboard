from io import BytesIO

import httpx
import numpy as np
import pandas as pd
import pytest

from src.providers import aaii, finra, public_http


def finra_raw(rows):
    # Official download inspected 2026-10-22: row 0 header, YYYY-MM strings,
    # newest observations first, numbers in USD millions, not dollars.
    return pd.DataFrame([["Year-Month", finra.DEBIT_HEADER, "Free Credit Balances"], *rows])


def aaii_raw(rows):
    # Official legacy XLS: split headers, fractional sentiment, summary footer.
    data = [list(row[:4]) + [None] * 8 + [row[4] if len(row) > 4 else 3000] for row in rows]
    return pd.DataFrame(
        [
            [None, None, None, "American Association of Individual Investors"],
            [None] * 12 + ["S&P 500"],
            ["Reported"] + [None] * 11 + ["Weekly"],
            ["Date", "Bullish", "Neutral", "Bearish"] + [None] * 6 + ["High", "Low", "Close"],
            [None, None, None, None],
            *data,
            ["Observations over life of survey", None, None, None],
            ["Avg", 0.376, 0.31, 0.314],
        ]
    )


def test_finra_source_layout_units_month_ends_and_gaps():
    raw = finra_raw([["2026-09", 1480054, 215328], ["2026-07", "1,417,225", 205132]])
    result = finra.parse_frame(raw, today="2026-10-22")
    assert result.index.tolist() == [pd.Timestamp("2026-07-31"), pd.Timestamp("2026-09-30")]
    assert result[finra.SERIES_ID].tolist() == [1417225.0, 1480054.0]
    assert result.attrs["units"] == "USD millions"
    assert result.attrs["missing_months"] == ["2026-08"]


@pytest.mark.parametrize("bad", [0, -1, np.inf, np.nan, "bad"])
def test_finra_rejects_bad_debit(bad):
    with pytest.raises(ValueError):
        finra.parse_frame(finra_raw([["2024-01", bad, 5]]), today="2026-10-22")


def test_finra_rejects_duplicate_future_and_changed_schema():
    for rows in [
        [["2024-01", 10, 5], ["2024-01", 10, 5]],
        [["2026-11", 10, 5]],
        [["Jan 24", 10, 5]],
    ]:
        with pytest.raises(ValueError):
            finra.parse_frame(finra_raw(rows), today="2026-10-22")
    with pytest.raises(ValueError, match="schema changed"):
        finra.parse_frame(pd.DataFrame([["Date", "Debt"], ["2024-01", 10]]))


def test_finra_actual_excel_decoding():
    output = BytesIO()
    finra_raw([["2026-09", 1480054, 215328]]).to_excel(output, index=False, header=False)
    result = finra.parse_workbook(output.getvalue(), today="2026-10-22")
    assert result.iloc[0, 0] == 1480054.0


def test_aaii_source_layout_percent_scale_reported_date_and_missing():
    raw = aaii_raw(
        [
            [pd.Timestamp("1987-06-26"), None, None, None],
            [pd.Timestamp("1987-07-24"), 0.36, 0.50, 0.14],
            [pd.Timestamp("2026-10-22"), 0.368715, 0.173184, 0.458101],
        ]
    )
    result = aaii.parse_frame(raw, today="2026-10-22")
    assert result.columns.tolist() == list(aaii.SERIES_IDS)
    assert result.index[-1] == pd.Timestamp("2026-10-22")
    assert result.iloc[0].tolist() == pytest.approx([36, 50, 14, 3000])
    assert result.iloc[-1].tolist() == pytest.approx([36.8715, 17.3184, 45.8101, 3000])
    assert result.attrs["missing_survey_dates"] == ["1987-06-26"]


def test_aaii_preserves_published_rounding_without_normalizing():
    raw = aaii_raw([[pd.Timestamp("2007-01-18"), 0.5778, 0.1515, 0.2727]])
    result = aaii.parse_frame(raw, today="2026-10-22")
    assert result.loc[:, list(aaii.SENTIMENT_IDS)].iloc[0].sum() == pytest.approx(100.2)


@pytest.mark.parametrize("bad", [0, -1, np.inf, "not a close"])
def test_aaii_invalid_weekly_close_rejects_whole_snapshot(bad):
    raw = aaii_raw([[pd.Timestamp("2026-10-22"), 0.36, 0.14, 0.50, bad]])
    with pytest.raises(ValueError, match="close"):
        aaii.parse_frame(raw, today="2026-10-22")


def test_aaii_missing_weekly_close_is_preserved_without_fill():
    raw = aaii_raw([[pd.Timestamp("2026-10-22"), 0.36, 0.14, 0.50, None]])
    result = aaii.parse_frame(raw, today="2026-10-22")
    assert pd.isna(result[aaii.PRICE_ID].iloc[0])
    assert result["AAII_BULLISH"].iloc[0] == 36


@pytest.mark.parametrize(
    "row",
    [
        ["Oct 21", 0.369, 0.173, 0.458],
        [pd.Timestamp("2026-10-29"), 0.369, 0.173, 0.458],
        [pd.Timestamp("2026-10-22"), 36.9, 17.3, 45.8],
        [pd.Timestamp("2026-10-22"), -0.1, 0.5, 0.6],
        [pd.Timestamp("2026-10-22"), np.inf, 0.2, 0.3],
        [pd.Timestamp("2026-10-22"), 0.3, None, 0.3],
        [pd.Timestamp("2026-10-22"), 0.3, 0.3, 0.3],
    ],
)
def test_aaii_rejects_ambiguous_dates_and_invalid_values(row):
    with pytest.raises(ValueError):
        aaii.parse_frame(aaii_raw([row]), today="2026-10-22")


def test_aaii_duplicate_dates_and_empty_history():
    row = [pd.Timestamp("2026-10-22"), 0.36, 0.14, 0.50]
    with pytest.raises(ValueError, match="Duplicate"):
        aaii.parse_frame(aaii_raw([row, row]), today="2026-10-22")
    with pytest.raises(ValueError, match="no sentiment"):
        aaii.parse_frame(aaii_raw([]), today="2026-10-22")


def test_provider_snapshot_and_date_bounds(monkeypatch):
    frame = aaii.parse_frame(
        aaii_raw(
            [
                [pd.Timestamp("2024-01-04"), 0.36, 0.14, 0.50],
                [pd.Timestamp("2024-01-11"), 0.40, 0.15, 0.45],
            ]
        ),
        today="2026-10-22",
    )
    calls = []
    monkeypatch.setattr(aaii, "fetch_workbook", lambda *args, **kwargs: calls.append(1))
    monkeypatch.setattr(aaii, "parse_workbook", lambda content: frame)
    provider = aaii.AaiiProvider()
    selected = provider.get_frame("2024-01-10", "2024-01-11")
    assert len(selected) == 1
    assert selected.index[0] == pd.Timestamp("2024-01-11")
    assert provider.get_history("AAII_BULLISH").iloc[0] == 36
    assert provider.get_history("AAII_BEARISH").iloc[-1] == 45
    assert len(calls) == 1
    with pytest.raises(ValueError, match="Unsupported"):
        provider.get_history("INVALID")
    with pytest.raises(ValueError, match="bounds"):
        provider.get_frame("2024-01-11", "2024-01-04")


def test_public_download_rejects_access_page_and_does_not_retry_403(monkeypatch):
    request = httpx.Request("GET", finra.DOWNLOAD_URL)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(1)
        return httpx.Response(403, request=request, text="access denied")

    monkeypatch.setattr(public_http.httpx, "get", forbidden)
    with pytest.raises(public_http.PublicSourceError, match="retained"):
        public_http.fetch_workbook(finra.DOWNLOAD_URL)
    assert len(calls) == 1
    monkeypatch.setattr(
        public_http.httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(200, request=request, text="<html>Log in</html>"),
    )
    with pytest.raises(public_http.PublicSourceError, match="expected workbook"):
        public_http.fetch_workbook(finra.DOWNLOAD_URL)


def test_public_download_retries_are_bounded(monkeypatch):
    calls, sleeps = [], []

    def unavailable(*args, **kwargs):
        calls.append(1)
        raise httpx.ConnectError("source unavailable")

    monkeypatch.setattr(public_http.httpx, "get", unavailable)
    monkeypatch.setattr(public_http.time, "sleep", sleeps.append)
    with pytest.raises(public_http.PublicSourceError):
        public_http.fetch_workbook(finra.DOWNLOAD_URL)
    assert len(calls) == 3
    assert sleeps == [1, 2]
