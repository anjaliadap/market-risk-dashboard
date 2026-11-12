"""FINRA customer debit balances, in USD millions, dated at calendar month end.

Official download contains history since January 1997. FINRA generally publishes
in the third week after the reference month; these are not intraday observations.
The historical FINRA/NYSE collection methodology changed in February 2010.
"""

import re
from io import BytesIO

import numpy as np
import pandas as pd

from src.providers.public_http import fetch_workbook, filter_history

SOURCE_URL = "https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics"
DOWNLOAD_URL = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"
SERIES_ID = "FINRA_MARGIN_DEBT"
DEBIT_HEADER = "Debit Balances in Customers' Securities Margin Accounts"


def parse_frame(raw: pd.DataFrame, *, today=None) -> pd.DataFrame:
    """Parse FINRA's actual workbook layout; never infer or interpolate missing balances."""
    header_row = None
    for i, row in raw.head(20).iterrows():
        labels = [str(value).strip() for value in row]
        if DEBIT_HEADER in labels and labels[0] in {"Year-Month", "Month/Year"}:
            header_row = i
            debit_column = labels.index(DEBIT_HEADER)
            break
    if header_row is None:
        raise ValueError(
            "FINRA workbook schema changed: month and customer debit columns not found"
        )

    dates, balances = [], []
    for row in raw.loc[header_row + 1 :].itertuples(index=False, name=None):
        month, value = row[0], row[debit_column]
        if pd.isna(month) and pd.isna(value):
            continue
        if not isinstance(month, str) or not re.fullmatch(r"\d{4}-\d{2}", month.strip()):
            raise ValueError(f"Invalid FINRA year-month: {month!r}")
        try:
            observation_date = pd.Period(month.strip(), freq="M").to_timestamp("M")
            balance = float(str(value).replace(",", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid FINRA date or debit balance") from exc
        dates.append(observation_date)
        balances.append(balance)

    if not dates:
        raise ValueError("FINRA workbook contains no observations")
    index = pd.DatetimeIndex(dates, name="date")
    values = np.asarray(balances, dtype=float)
    cutoff = (
        pd.Timestamp(today) if today is not None else pd.Timestamp.now(tz="UTC").tz_localize(None)
    )
    if index.duplicated().any():
        raise ValueError("Duplicate FINRA reference months")
    if (index > cutoff.normalize()).any():
        raise ValueError("Future FINRA reference month")
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("FINRA debit balances must be finite, positive USD millions")
    frame = pd.DataFrame({SERIES_ID: values}, index=index).sort_index()
    expected = pd.period_range(frame.index.min(), frame.index.max(), freq="M")
    missing = expected.difference(frame.index.to_period("M"))
    frame.attrs.update(
        source_url=SOURCE_URL,
        download_url=DOWNLOAD_URL,
        units="USD millions",
        date_basis="calendar month end of reference month",
        missing_months=missing.astype(str).tolist(),
    )
    return frame


def parse_workbook(content: bytes, *, today=None) -> pd.DataFrame:
    return parse_frame(pd.read_excel(BytesIO(content), header=None, engine="openpyxl"), today=today)


class FinraProvider:
    def get_frame(self) -> pd.DataFrame:
        return parse_workbook(fetch_workbook(DOWNLOAD_URL))

    def get_history(self, series_id, start_date="1997-01-01", end_date=None):
        if series_id != SERIES_ID:
            raise ValueError(f"Unsupported FINRA series: {series_id}")
        return filter_history(self.get_frame()[series_id], start_date, end_date)

    def get_latest(self, series_id):
        return self.get_history(series_id).iloc[-1]
