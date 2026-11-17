"""Official AAII weekly sentiment history, in percent (0 to 100).

Dates are the workbook's full Reported Date, not the website's previous-day
survey week-ending label. The legacy XLS stores sentiment fractions, which are
multiplied by 100 exactly once. The additional S&P 500 Weekly Close is the
AAII-reported index level, not an execution price or a dividend total return.
Source precision is retained; rows are not renormalized.
"""

import re
from datetime import date, datetime
from io import BytesIO

import numpy as np
import pandas as pd

from src.providers.public_http import fetch_workbook, filter_history

SOURCE_URL = "https://www.aaii.com/sentimentsurvey/sent_results"
DOWNLOAD_URL = "https://www.aaii.com/files/surveys/sentiment.xls"
SENTIMENT_IDS = ("AAII_BULLISH", "AAII_NEUTRAL", "AAII_BEARISH")
PRICE_ID = "AAII_SP500_WEEKLY_CLOSE"
SERIES_IDS = (*SENTIMENT_IDS, PRICE_ID)
# The published 2007-01-18 fractions sum to 1.002. Tolerate source rounding
# up to 0.25 percentage points without altering or scaling the three components.
SUM_TOLERANCE_PP = 0.25


def _reported_date(value):
    if isinstance(value, (datetime, date, pd.Timestamp, np.datetime64)):
        parsed = pd.Timestamp(value)
    elif isinstance(value, str) and re.fullmatch(
        r"(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}/\d{1,2}/\d{4})", value.strip()
    ):
        parsed = pd.Timestamp(value.strip())
    else:
        raise ValueError(f"AAII reported date must include an explicit year: {value!r}")
    if pd.isna(parsed) or parsed.tzinfo is not None or parsed != parsed.normalize():
        raise ValueError("Invalid AAII reported date")
    return parsed


def parse_frame(raw: pd.DataFrame, *, today=None) -> pd.DataFrame:
    """Parse the official XLS header, data block, and documented summary footer."""
    header_row = None
    for i, row in raw.head(20).iterrows():
        labels = [str(value).strip() for value in row]
        if labels[:4] == ["Date", "Bullish", "Neutral", "Bearish"]:
            header_row = i
            break
    if header_row is None:
        raise ValueError(
            "AAII workbook schema changed: Date/Bullish/Neutral/Bearish header missing"
        )
    if (
        raw.shape[1] < 13
        or [str(value).strip() for value in raw.loc[header_row].iloc[10:13]]
        != ["High", "Low", "Close"]
        or header_row < 2
        or str(raw.loc[header_row - 2].iloc[12]).strip() != "S&P 500"
        or str(raw.loc[header_row - 1].iloc[12]).strip() != "Weekly"
    ):
        raise ValueError("AAII workbook schema changed: S&P 500 Weekly Close column missing")

    dates, values, all_dates, missing = [], [], [], []
    cutoff = (
        pd.Timestamp(today) if today is not None else pd.Timestamp.now(tz="UTC").tz_localize(None)
    )
    for row in raw.loc[header_row + 1 :].itertuples(index=False, name=None):
        day, *components = row[:4]
        if isinstance(day, str) and day.strip() == "Observations over life of survey":
            break
        if pd.isna(day) and all(pd.isna(value) for value in components):
            continue
        reported = _reported_date(day)
        all_dates.append(reported)
        if reported > cutoff.normalize():
            raise ValueError("Future AAII reported date")
        if all(pd.isna(value) for value in components):
            missing.append(reported.date().isoformat())
            continue
        try:
            fractions = np.asarray(components, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError("Non-numeric AAII sentiment value") from exc
        if not np.isfinite(fractions).all() or (fractions < 0).any() or (fractions > 1).any():
            raise ValueError("AAII XLS sentiment values must be finite fractions between 0 and 1")
        percentages = fractions * 100
        if abs(percentages.sum() - 100) > SUM_TOLERANCE_PP + 1e-9:
            raise ValueError("AAII bullish, neutral and bearish percentages do not sum to 100")
        try:
            close = np.nan if pd.isna(row[12]) else float(row[12])
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid AAII-reported weekly S&P 500 close") from exc
        if not pd.isna(close) and (not np.isfinite(close) or close <= 0):
            raise ValueError("AAII-reported weekly S&P 500 close must be finite and positive")
        dates.append(reported)
        values.append([*percentages, close])

    if pd.DatetimeIndex(all_dates).duplicated().any():
        raise ValueError("Duplicate AAII reported dates")
    if not dates:
        raise ValueError("AAII workbook contains no sentiment observations")
    frame = pd.DataFrame(values, index=pd.DatetimeIndex(dates, name="date"), columns=SERIES_IDS)
    frame = frame.sort_index()
    frame.attrs.update(
        source_url=SOURCE_URL,
        download_url=DOWNLOAD_URL,
        units={**dict.fromkeys(SENTIMENT_IDS, "percent"), PRICE_ID: "index points"},
        date_basis="AAII workbook Reported Date",
        missing_survey_dates=missing,
    )
    return frame


def parse_workbook(content: bytes, *, today=None) -> pd.DataFrame:
    return parse_frame(pd.read_excel(BytesIO(content), header=None, engine="xlrd"), today=today)


class AaiiProvider:
    def __init__(self):
        self._frame = None

    def get_frame(self, start_date="1987-01-01", end_date=None) -> pd.DataFrame:
        # One provider is created for each refresh. Reuse this validated frame for
        # all component series so they always share one source snapshot.
        if self._frame is None:
            self._frame = parse_workbook(fetch_workbook(DOWNLOAD_URL, legacy_xls=True))
        return filter_history(self._frame.copy(), start_date, end_date)

    def get_history(self, series_id, start_date="1997-01-01", end_date=None):
        if series_id not in SERIES_IDS:
            raise ValueError(f"Unsupported AAII series: {series_id}")
        return filter_history(self.get_frame()[series_id], start_date, end_date).dropna()

    def get_latest(self, series_id):
        return self.get_history(series_id).iloc[-1]
