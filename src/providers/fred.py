import time
from io import StringIO

import httpx
import numpy as np
import pandas as pd


def parse_csv(text):
    if text.lstrip().lower().startswith(("<!doctype html", "<html")):
        raise ValueError(
            "FRED returned an HTML maintenance/error page instead of CSV; existing observations retained"
        )
    frame = pd.read_csv(StringIO(text), na_values=["."])
    if len(frame.columns) != 2:
        raise ValueError("Expected date and value columns")
    dates = pd.to_datetime(frame.iloc[:, 0], errors="raise")
    values = pd.to_numeric(frame.iloc[:, 1], errors="raise")
    if values.notna().sum() == 0:
        raise ValueError("No numeric observations")
    if np.isinf(values.dropna()).any() or dates.duplicated().any():
        raise ValueError("Infinite values or duplicate dates")
    return pd.Series(values.to_numpy(), index=dates).dropna().sort_index()


class FredProvider:
    def get_history(self, series_id, start_date="2000-01-01", end_date=None):
        params = {"id": series_id, "cosd": start_date}
        if end_date:
            params["coed"] = end_date
        for attempt in range(3):
            try:
                response = httpx.get(
                    "https://fred.stlouisfed.org/graph/fredgraph.csv",
                    params=params,
                    timeout=30,
                    follow_redirects=True,
                )
                response.raise_for_status()
                return parse_csv(response.text)
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt == 2:
                    raise
                if isinstance(exc, httpx.ProxyError):
                    raise
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    raise
                time.sleep(2**attempt)

    def get_latest(self, series_id):
        return self.get_history(series_id).iloc[-1]

    def get_metadata(self, series_id):
        from src.registry import BY_ID

        return BY_ID[series_id]
