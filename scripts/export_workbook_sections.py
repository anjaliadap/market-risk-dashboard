"""Export the three workbook sections from saved observations, without fetching data.

Run ``python -m scripts.export_workbook_sections`` after refreshing sources.
Consumers must read manifest.json, then the immutable CSV paths listed in it.
Publishing the manifest last is the atomic boundary for the complete batch.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.analytics.btc import coverage_snapshot
from src.analytics.margin_debt import peak_comparison, quarterly_ratio
from src.analytics.sentiment import decile_returns, spread_history
from src.database import store
from src.providers.workbook_sections import AAII_IDS, SECTION_IDS, STRATEGY_IDS, validate_history
from src.registry import BY_ID

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "workbook_sections"

README = """# Workbook section exports

Read `manifest.json` first, then read the relative immutable paths in its `files`
mapping. All listed files belong to that one generation. The manifest is replaced
atomically only after the complete batch is written. Failed validation or writes
preserve the previously published manifest and its files. Older snapshots remain
available for consumers already reading them. Never select files by directory
sorting or combine files from different generations.

`margin_debt.csv` outer-joins the matched quarterly GDP and public-equity proxy
calculations. `margin_debt_gdp.csv` and `margin_debt_equity_proxy.csv` retain each
ratio's own matched periods. FINRA balances and Fed public equity market value are
USD millions; nominal GDP is USD billions at a seasonally adjusted annual rate.
Ratios and historical means are percentage points (2.4 means 2.4%). FRED quarterly
date labels are normalized to quarter end. Missing periods are never filled.
The Fed public-equity series is a quarterly proxy with different coverage from
the workbook's monthly Wilshire 5000 capitalization. Historical peak/trough
comparisons use the workbook's rounded reference milestones, not newly detected
market cycles.

`bull_vs_bear.csv` contains AAII percent sentiment, bull-minus-bear percentage
point spread, full-sample rounded inclusive percentiles, deciles, and forward
S&P 500 PRICE returns. AAII-reported weekly closes exclude dividends; they do
not reproduce Bloomberg total returns. Dates preserve AAII's Reported Date,
whose exact underlying market close timestamp is not supplied. Return endpoints
use the first close on or after each calendar-month horizon within seven days.
Unmatured horizons and missing observations stay blank. Decile statistics include
valid sample counts. Full-sample ranks change when history expands and overlapping
weekly windows are descriptive, not a point-in-time trading backtest.

`btc.csv` reports Strategy holdings coverage using the saved Coinbase spot quote,
Strategy debt plus preferred notional, and average acquisition cost per BTC.
Monetary amount rows are USD millions unless their unit states USD/BTC. The
quote's actual source timestamp and the company's separate snapshot date are in
the manifest. Saved inputs may be delayed or stale; see each source status before
using the output. Manifest observation dates retain raw source labels, while
quarterly freshness uses the corresponding reference quarter end. Strategy
freshness uses each component's published as-of date when supplied; ledger cost
basis can predate the statistics snapshot. This simplified asset-coverage table
is not a default estimate.

No exporter action retrieves a network source or substitutes invented values.
Refresh first with `python -m scripts.refresh_workbook_sections`, then export with
`python -m scripts.export_workbook_sections --output-dir data/workbook_sections`.
"""


def _utc(value):
    if value is None or pd.isna(value):
        return None
    stamp = pd.Timestamp(value)
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    return stamp.isoformat().replace("+00:00", "Z")


def _saved_inputs():
    histories = {key: store.history(key) for key in SECTION_IDS}
    missing = [key for key, frame in histories.items() if frame.empty]
    if missing:
        raise ValueError("Missing saved source inputs: " + ", ".join(missing))
    for key, frame in histories.items():
        validate_history(frame.value, BY_ID[key])
        if not frame.units.eq(BY_ID[key]["unit"]).all():
            raise ValueError(f"Saved units do not match the source registry for {key}")
    return histories


def _sentiment(histories):
    components = pd.concat([histories[key].value.rename(key) for key in AAII_IDS[:3]], axis=1)
    if components.isna().any().any():
        raise ValueError("AAII sentiment components do not share the same reported dates")
    if ((components < 0) | (components > 100)).any().any() or (
        abs(components.sum(axis=1) - 100) > 0.25 + 1e-9
    ).any():
        raise ValueError("Saved AAII percentages fail range or sum checks")
    vintages = pd.concat([histories[key].retrieved_at.rename(key) for key in AAII_IDS], axis=1)
    if (vintages.nunique(axis=1) > 1).any():
        raise ValueError("AAII fields do not share a coherent saved source snapshot")
    spreads = spread_history(components.AAII_BULLISH, components.AAII_BEARISH)
    if spreads.empty:
        raise ValueError("No matched AAII sentiment observations")
    prices = histories["AAII_SP500_WEEKLY_CLOSE"].value
    if (prices <= 0).any():
        raise ValueError("Saved AAII weekly S&P 500 closes must be positive")
    summary, detail = decile_returns(spreads, prices)
    detail = detail.join(components.AAII_NEUTRAL.rename("neutral_pct"))
    detail = detail.join(prices.rename("aaii_sp500_weekly_close_index_points"))
    detail.index.name = "reported_date"
    return summary, detail


def _btc(histories):
    dates = {histories[key].index[-1] for key in STRATEGY_IDS}
    vintages = {histories[key].retrieved_at.iloc[-1] for key in STRATEGY_IDS}
    if len(dates) != 1 or len(vintages) != 1:
        raise ValueError("Strategy fields do not share one saved source snapshot")
    quote = histories["COINBASE_BTC_SPOT"]
    if pd.isna(quote.published_at.iloc[-1]):
        raise ValueError("Saved BTC spot quote is missing its actual source timestamp")
    values = {key: histories[key].value.iloc[-1] for key in STRATEGY_IDS}
    result = coverage_snapshot(
        values["STRATEGY_BTC_HOLDINGS"],
        quote.value.iloc[-1],
        values["STRATEGY_DEBT_USD"],
        values["STRATEGY_PREFERRED_USD"],
        values["STRATEGY_BTC_COST_USD"],
    )
    rows = [
        ("BTC position", result["holdings_btc"], "BTC"),
        ("BTC price", result["btc_price_usd"], "USD/BTC"),
        ("BTC market value", result["btc_market_value_usdm"], "USD millions"),
        ("Total debt + preferred", result["debt_preferred_usdm"], "USD millions"),
        ("Loan to value", result["ltv_pct"], "percent"),
        ("BTC / debt + preferred coverage", result["coverage_x"], "times"),
        ("BTC price for 1:1 coverage", result["breakeven_btc_price_usd"], "USD/BTC"),
        ("Downside vs current price", result["downside_pct"], "percent"),
        ("Cost basis", result["cost_basis_usd"], "USD/BTC"),
        ("Unrealized gain / loss", result["gain_loss_usdm"], "USD millions"),
    ]
    return pd.DataFrame(rows, columns=["metric", "value", "units"])


def _calculations(histories):
    debt = histories["FINRA_MARGIN_DEBT"].value
    gdp = quarterly_ratio(debt, histories["GDP"].value, denominator_unit="USD billions")
    equity = quarterly_ratio(
        debt,
        histories["BOGZ1LM883164115Q"].value,
        denominator_unit="USD millions",
        start="1997-01-01",
    )
    if gdp.empty or equity.empty:
        raise ValueError("No matched quarter-end periods for a required margin denominator")
    margin = gdp.rename(
        columns={
            "margin_usd_millions": "gdp_margin_usd_millions",
            "denominator": "nominal_gdp_usd_billions",
            "ratio_pct": "margin_to_gdp_pct",
            "historical_mean_pct": "margin_to_gdp_historical_mean_pct",
        }
    ).join(
        equity.rename(
            columns={
                "margin_usd_millions": "equity_margin_usd_millions",
                "denominator": "fed_public_equity_value_usd_millions",
                "ratio_pct": "margin_to_fed_public_equity_proxy_pct",
                "historical_mean_pct": "margin_to_fed_public_equity_proxy_historical_mean_pct",
            }
        ),
        how="outer",
    )
    margin.insert(
        0,
        "margin_usd_millions",
        margin.gdp_margin_usd_millions.combine_first(margin.equity_margin_usd_millions),
    )
    margin = margin.drop(columns=["gdp_margin_usd_millions", "equity_margin_usd_millions"])
    summary, sentiment = _sentiment(histories)
    return {
        "margin_debt.csv": margin,
        "margin_debt_gdp.csv": gdp,
        "margin_debt_equity_proxy.csv": equity,
        "margin_debt_peak_comparisons.csv": peak_comparison(debt.iloc[-1]),
        "bull_vs_bear.csv": sentiment,
        "bull_vs_bear_decile_statistics.csv": summary,
        "btc.csv": _btc(histories),
    }


def _sources(histories, now):
    with Session(store.engine) as session:
        jobs = session.scalars(select(store.Job).order_by(store.Job.started_at, store.Job.id)).all()
        latest_jobs = {job.series_id: job for job in jobs}
    sources = {}
    for key, frame in histories.items():
        meta = BY_ID[key]
        last = frame.iloc[-1]
        saved_metadata = store.source_metadata(key)
        reference_date = frame.index[-1]
        reference_period_end = None
        component_date = None
        if meta["frequency"] == "quarterly":
            reference_date = reference_date.to_period("Q").end_time.normalize()
            reference_period_end = reference_date.date().isoformat()
        if key in STRATEGY_IDS:
            component_date = saved_metadata.get("component_as_of_dates", {}).get(key)
            if component_date:
                reference_date = pd.Timestamp(component_date).normalize()
                component_date = reference_date.date().isoformat()
        age_days = (pd.Timestamp(now).tz_localize(None) - reference_date).days
        stale = age_days > meta.get("stale_days", 200 if meta["frequency"] == "quarterly" else 14)
        quote_time = _utc(last.published_at)
        if key == "COINBASE_BTC_SPOT":
            quote_age = pd.Timestamp(now).to_pydatetime() - pd.Timestamp(quote_time).to_pydatetime()
            stale = quote_age > timedelta(minutes=15)
        job = latest_jobs.get(key)
        sources[key] = {
            "name": meta["name"],
            "source_url": meta["url"],
            "endpoint": meta.get("endpoint"),
            "units": meta["unit"],
            "frequency": meta["frequency"],
            "observations": len(frame),
            "first_observation_date": frame.index[0].date().isoformat(),
            "latest_observation_date": frame.index[-1].date().isoformat(),
            "latest_reference_period_end": reference_period_end,
            "latest_component_as_of_date": component_date,
            "freshness_reference_date": reference_date.date().isoformat(),
            "latest_observation_retrieved_at_utc": _utc(last.retrieved_at),
            "quote_source_time_utc": quote_time,
            "status": "STALE / SAVED" if stale else "AVAILABLE / DELAYED",
            "last_refresh_status": job.status if job is not None else "Not recorded",
            "last_refresh_attempt_utc": _utc(job.started_at) if job is not None else None,
            "last_refresh_error": job.error if job is not None else None,
            "saved_source_metadata": saved_metadata,
        }
    return sources


def export_sections(output_dir=DEFAULT_OUTPUT_DIR):
    """Publish an immutable generation; validation failure never changes prior exports."""
    store.initialize()
    histories = _saved_inputs()
    frames = _calculations(histories)
    now = datetime.now(UTC)
    generation = now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
    manifest = {
        "schema_version": 1,
        "generation": generation,
        "generated_at_utc": _utc(now),
        "network_fetch_performed": False,
        "consumer_contract": "Read this manifest once, then its immutable relative file paths; never mix generations.",
        "sources": _sources(histories, now),
        "files": {},
        "semantics": {
            "margin": "Quarterly Fed public equity proxy differs from monthly Wilshire capitalization; ratios are percent; no fill.",
            "sentiment": "AAII full-sample deciles; weekly S&P 500 price returns exclude dividends; completed horizons only.",
            "btc": "Debt plus preferred notional; company snapshot and quote source timestamp are separate.",
        },
    }
    payloads = {}
    for name, frame in frames.items():
        include_index = name not in {"btc.csv", "margin_debt_peak_comparisons.csv"}
        payload = frame.to_csv(index=include_index).encode("utf-8")
        payloads[name] = payload
        manifest["files"][name] = {
            "path": f"snapshots/{generation}/{name}",
            "rows": len(frame),
            "columns": frame.columns.tolist(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    payloads["README.md"] = README.encode("utf-8")
    manifest["files"]["README.md"] = {
        "path": f"snapshots/{generation}/README.md",
        "sha256": hashlib.sha256(payloads["README.md"]).hexdigest(),
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshots = output_dir / "snapshots"
    snapshots.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=output_dir))
    destination = snapshots / generation
    manifest_temp = output_dir / (".manifest-" + generation + ".tmp")
    committed = False
    try:
        for name, payload in payloads.items():
            (staging / name).write_bytes(payload)
        os.replace(staging, destination)
        with manifest_temp.open("wb") as handle:
            handle.write(
                (json.dumps(manifest, indent=2, allow_nan=False, default=str) + "\n").encode()
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(manifest_temp, output_dir / "manifest.json")
        committed = True
        return manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if not committed:
            shutil.rmtree(destination, ignore_errors=True)
            manifest_temp.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    try:
        manifest = export_sections(args.output_dir)
    except (ValueError, OSError, SQLAlchemyError) as exc:
        print(f"Workbook section export failed: {exc}. Previous exports retained.", file=sys.stderr)
        return 1
    print(f"Published {manifest['generation']} via {args.output_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
