import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd
import pytest
from sqlalchemy import create_engine, delete, update
from sqlalchemy.orm import Session

from scripts import export_workbook_sections as exports
from src.database import store
from src.providers.workbook_sections import AAII_IDS, STRATEGY_IDS
from src.registry import BY_ID


@pytest.fixture
def export_database(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "export.db"))
    monkeypatch.setattr(store, "engine", engine)
    store.initialize()

    def no_network(*args, **kwargs):
        raise AssertionError("Export must never retrieve a network source")

    monkeypatch.setattr(httpx, "get", no_network)
    yield tmp_path / "exported"
    engine.dispose()


@pytest.fixture
def populated_export(export_database):
    margin = pd.Series([500_000.0, 600_000.0], index=pd.to_datetime(["2024-03-29", "2024-06-28"]))
    gdp = pd.Series([25_000.0], index=pd.to_datetime(["2024-01-01"]))
    equity = pd.Series(
        [25_000_000.0, 30_000_000.0], index=pd.to_datetime(["2024-01-01", "2024-04-01"])
    )
    for key, values in [("FINRA_MARGIN_DEBT", margin), ("GDP", gdp), ("BOGZ1LM883164115Q", equity)]:
        store.save(BY_ID[key], values)
    surveys = pd.DataFrame(
        [[30, 20, 50, 100], [40, 20, 40, 110], [50, 20, 30, 99]],
        index=pd.to_datetime(["2024-01-04", "2024-02-04", "2024-03-04"]),
        columns=AAII_IDS,
    )
    store.save_many([(BY_ID[key], surveys[key]) for key in AAII_IDS])
    values = [1000.0, 20_000_000.0, 5_000_000.0, 60_000.0]
    company = []
    for key, value in zip(STRATEGY_IDS, values, strict=True):
        source = pd.Series([value], index=pd.to_datetime(["2024-03-01"]))
        source.attrs["source_date"] = "2024-03-01"
        company.append((BY_ID[key], source))
    store.save_many(company)
    now = datetime.now(UTC)
    quote = pd.Series(
        [100_000.0], index=pd.DatetimeIndex([pd.Timestamp(now).tz_localize(None).normalize()])
    )
    quote.attrs["published_at"] = now
    store.save(BY_ID["COINBASE_BTC_SPOT"], quote)
    return export_database


def read_csv(output, manifest, name, **kwargs):
    return pd.read_csv(output / manifest["files"][name]["path"], **kwargs)


def published_bytes(output):
    return {
        str(path.relative_to(output)): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    }


def test_exported_named_sections_use_saved_values_and_explicit_metadata(populated_export):
    manifest = exports.export_sections(populated_export)
    on_disk = json.loads((populated_export / "manifest.json").read_text())
    assert on_disk == manifest
    assert not manifest["network_fetch_performed"]
    assert set(manifest["files"]) == {
        "margin_debt.csv",
        "margin_debt_gdp.csv",
        "margin_debt_equity_proxy.csv",
        "margin_debt_peak_comparisons.csv",
        "bull_vs_bear.csv",
        "bull_vs_bear_decile_statistics.csv",
        "btc.csv",
        "README.md",
    }
    for entry in manifest["files"].values():
        payload = (populated_export / entry["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
    btc = read_csv(populated_export, manifest, "btc.csv").set_index("metric")
    assert len(btc) == 10
    assert btc.loc["BTC market value", "value"] == pytest.approx(100)
    assert btc.loc["Total debt + preferred", "value"] == pytest.approx(25)
    assert btc.loc["BTC / debt + preferred coverage", "value"] == pytest.approx(4)
    assert btc.loc["BTC price for 1:1 coverage", "value"] == pytest.approx(25_000)
    assert btc.loc["Downside vs current price", "value"] == pytest.approx(-75)
    assert btc.loc["Unrealized gain / loss", "value"] == pytest.approx(40)
    assert btc.loc["BTC market value", "units"] == "USD millions"
    sources = manifest["sources"]
    assert sources["FINRA_MARGIN_DEBT"]["units"] == "USD millions"
    assert sources["GDP"]["units"] == "billions USD SAAR"
    assert sources["AAII_BULLISH"]["source_url"].startswith("https://www.aaii.com/")
    assert sources["COINBASE_BTC_SPOT"]["quote_source_time_utc"].endswith("Z")
    assert sources["STRATEGY_DEBT_USD"]["latest_observation_date"] == "2024-03-01"
    assert sources["STRATEGY_DEBT_USD"]["latest_observation_retrieved_at_utc"].endswith("Z")
    assert sources["STRATEGY_DEBT_USD"]["saved_source_metadata"]["source_date"] == "2024-03-01"
    assert "price returns exclude dividends" in manifest["semantics"]["sentiment"]


def test_margin_outer_join_never_fills_an_unavailable_gdp_quarter(populated_export):
    manifest = exports.export_sections(populated_export)
    main = read_csv(populated_export, manifest, "margin_debt.csv", index_col="quarter_end")
    assert main.index.tolist() == ["2024-03-31", "2024-06-30"]
    assert main.loc["2024-03-31", "margin_to_gdp_pct"] == pytest.approx(2)
    assert pd.isna(main.loc["2024-06-30", "margin_to_gdp_pct"])
    assert pd.isna(main.loc["2024-06-30", "nominal_gdp_usd_billions"])
    assert main.loc["2024-06-30", "margin_to_fed_public_equity_proxy_pct"] == pytest.approx(2)
    assert main.margin_usd_millions.tolist() == [500_000, 600_000]
    assert len(read_csv(populated_export, manifest, "margin_debt_gdp.csv")) == 1
    assert len(read_csv(populated_export, manifest, "margin_debt_equity_proxy.csv")) == 2


def test_sentiment_exports_missing_horizons_as_blanks_and_counts_only_matured_rows(
    populated_export,
):
    manifest = exports.export_sections(populated_export)
    sentiment = read_csv(populated_export, manifest, "bull_vs_bear.csv", index_col="reported_date")
    assert sentiment.spread_pp.tolist() == [-20, 0, 20]
    assert sentiment.percentile.tolist() == [0, 50, 100]
    assert sentiment.decile.tolist() == [1, 5, 10]
    assert sentiment["1M"].iloc[:2].tolist() == pytest.approx([10, -10])
    assert pd.isna(sentiment["1M"].iloc[-1])
    assert sentiment[["3M", "6M", "12M"]].isna().all().all()
    summary = read_csv(
        populated_export, manifest, "bull_vs_bear_decile_statistics.csv", index_col="Decile"
    )
    assert summary["1M n"].sum() == 2
    assert summary["3M n"].sum() == 0
    assert pd.isna(summary.loc[10, "1M mean (%)"])


@pytest.mark.parametrize("missing", ["GDP", "STRATEGY_PREFERRED_USD", "AAII_NEUTRAL"])
def test_missing_required_input_preserves_every_previous_export(populated_export, missing):
    exports.export_sections(populated_export)
    before = published_bytes(populated_export)
    with Session(store.engine) as session, session.begin():
        session.execute(delete(store.Observation).where(store.Observation.series_id == missing))
    with pytest.raises(ValueError, match="Missing saved source inputs"):
        exports.export_sections(populated_export)
    assert published_bytes(populated_export) == before


def test_invalid_saved_units_do_not_publish_a_new_batch(populated_export):
    exports.export_sections(populated_export)
    before = published_bytes(populated_export)
    with Session(store.engine) as session, session.begin():
        session.execute(
            update(store.Observation)
            .where(store.Observation.series_id == "FINRA_MARGIN_DEBT")
            .values(units="USD billions")
        )
    with pytest.raises(ValueError, match="units"):
        exports.export_sections(populated_export)
    assert published_bytes(populated_export) == before


def test_incoherent_strategy_snapshot_never_publishes_coverage(populated_export):
    exports.export_sections(populated_export)
    before = published_bytes(populated_export)
    debt = pd.Series([21_000_000.0], index=pd.to_datetime(["2024-03-01"]))
    store.save(BY_ID["STRATEGY_DEBT_USD"], debt)
    with pytest.raises(ValueError, match="one saved source snapshot"):
        exports.export_sections(populated_export)
    assert published_bytes(populated_export) == before


def test_staging_write_failure_keeps_published_generation(populated_export, monkeypatch):
    exports.export_sections(populated_export)
    before = published_bytes(populated_export)
    write_bytes = Path.write_bytes

    def fail_one_write(path, content):
        if path.name == "btc.csv":
            raise OSError("simulated disk write failure")
        return write_bytes(path, content)

    monkeypatch.setattr(Path, "write_bytes", fail_one_write)
    with pytest.raises(OSError, match="disk write failure"):
        exports.export_sections(populated_export)
    assert published_bytes(populated_export) == before
    assert not list(populated_export.glob(".staging-*"))


def test_manifest_publish_failure_keeps_old_manifest_and_files(populated_export, monkeypatch):
    exports.export_sections(populated_export)
    before = published_bytes(populated_export)
    replace = exports.os.replace

    def fail_commit(source, destination):
        if Path(destination).name == "manifest.json":
            raise OSError("simulated manifest publication failure")
        return replace(source, destination)

    monkeypatch.setattr(exports.os, "replace", fail_commit)
    with pytest.raises(OSError, match="publication failure"):
        exports.export_sections(populated_export)
    assert published_bytes(populated_export) == before
    assert not list(populated_export.glob(".manifest-*.tmp"))


def test_cli_missing_data_returns_nonzero_with_explicit_error(export_database, capsys):
    assert exports.main(["--output-dir", str(export_database)]) == 1
    error = capsys.readouterr().err
    assert "Missing saved source inputs" in error
    assert "FINRA_MARGIN_DEBT" in error
    assert "Previous exports retained" in error
    assert not export_database.exists()


def test_quarterly_freshness_uses_reference_end_and_preserves_raw_fred_label(export_database):
    gdp = pd.Series([30_000.0], index=pd.to_datetime(["2026-04-01"]))
    store.save(BY_ID["GDP"], gdp)
    sources = exports._sources({"GDP": store.history("GDP")}, pd.Timestamp("2026-10-22T12:00:00Z"))
    source = sources["GDP"]
    assert source["latest_observation_date"] == "2026-04-01"
    assert source["latest_reference_period_end"] == "2026-06-30"
    assert source["freshness_reference_date"] == "2026-06-30"
    assert source["status"] == "AVAILABLE / DELAYED"
    assert source["units"] == "billions USD SAAR"
    assert source["frequency"] == "quarterly"


def test_strategy_component_freshness_uses_ledger_date_separately_from_snapshot(export_database):
    component_dates = {
        "STRATEGY_BTC_HOLDINGS": "2026-10-20",
        "STRATEGY_BTC_COST_USD": "2026-09-01",
    }
    inputs = []
    for key, value in [("STRATEGY_BTC_HOLDINGS", 1000), ("STRATEGY_BTC_COST_USD", 60_000)]:
        values = pd.Series([value], index=pd.to_datetime(["2026-10-20"]))
        values.attrs["component_as_of_dates"] = component_dates
        inputs.append((BY_ID[key], values))
    store.save_many(inputs)
    sources = exports._sources(
        {key: store.history(key) for key in component_dates},
        pd.Timestamp("2026-10-22T12:00:00Z"),
    )
    holdings = sources["STRATEGY_BTC_HOLDINGS"]
    cost = sources["STRATEGY_BTC_COST_USD"]
    assert holdings["latest_observation_date"] == cost["latest_observation_date"] == "2026-10-20"
    assert holdings["status"] == "AVAILABLE / DELAYED"
    assert cost["status"] == "STALE / SAVED"
    assert cost["latest_component_as_of_date"] == "2026-09-01"
    assert cost["freshness_reference_date"] == "2026-09-01"
    assert cost["latest_reference_period_end"] is None
    assert cost["units"] == "USD/BTC"
