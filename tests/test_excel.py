import copy
import hashlib
import json
from datetime import datetime
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from openpyxl import Workbook

from src import excel_sync
from src.providers.excel import ExcelWorkbookProvider, normalize_date


@pytest.fixture
def mapping():
    return {
        "version": 1,
        "sections": {
            "Market Data": {
                "sheets": ["History", "Snapshot"],
                "notes": ["Manual benchmark"],
                "charts": [
                    {
                        "id": "prices",
                        "title": "Saved prices",
                        "series": [
                            {
                                "id": "price",
                                "name": "Price",
                                "sheet": "History",
                                "values": "B2:B3",
                                "date_sheet": "History",
                                "dates": "A2:A3",
                                "kind": "LineChart",
                                "secondary": False,
                                "unit": "General",
                                "expected_number_format": "General",
                                "value_type": "number",
                            }
                        ],
                    }
                ],
                "tables": [
                    {
                        "id": "benchmarks",
                        "title": "Benchmarks",
                        "sheet": "Snapshot",
                        "range": "A1:B2",
                        "date_cell": None,
                        "expected_headers": {"A1": "Benchmark"},
                    }
                ],
            }
        },
    }


def workbook_bytes(formula="=100+10", cached="110", value=120, unit="General"):
    book = Workbook()
    sheet = book.active
    sheet.title = "History"
    sheet.append(["Date", "Price"])
    sheet.append([datetime(2024, 1, 31), formula])
    sheet.append([datetime(2024, 2, 29), value])
    sheet["B3"].number_format = unit
    other = book.create_sheet("Snapshot")
    other.append(["Benchmark", "Value"])
    other.append(["Fixed", 90])
    stream = BytesIO()
    book.save(stream)
    out = BytesIO()
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(stream) as source, ZipFile(out, "w") as dest:
        for item in source.infolist():
            blob = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml" and cached is not None:
                root = ET.fromstring(blob)
                cell = root.find(".//m:c[@r='B2']", ns)
                cell.find("m:v", ns).text = str(cached)
                blob = ET.tostring(root)
            dest.writestr(item, blob)
    return out.getvalue()


def test_saved_caches_metadata_and_source_preserved(tmp_path, mapping):
    path = tmp_path / "master.xlsx"
    blob = workbook_bytes()
    path.write_bytes(blob)
    snapshot = ExcelWorkbookProvider(path, mapping).read()
    series = snapshot["sections"]["Market Data"]["charts"][0]["series"][0]
    assert [p["value"] for p in series["points"]] == [110, 120]
    assert series["points"][0]["formula"] == "=100+10"
    assert series["points"][0]["date"] == "2024-01-31"
    assert snapshot["sha256"] == hashlib.sha256(blob).hexdigest()
    assert path.read_bytes() == blob
    assert snapshot["sections"]["Market Data"]["tables"][0]["rows"][1][1]["value"] == 90
    assert "Unknown" in snapshot["refresh_attestation"]


def test_missing_formula_cache_never_evaluated(tmp_path, mapping):
    provider = ExcelWorkbookProvider(tmp_path / "not-written.xlsx", mapping)
    snapshot = provider.read_bytes(workbook_bytes(cached=None))
    assert snapshot["diagnostics"]["missing_formula_caches"] == 1
    points = snapshot["sections"]["Market Data"]["charts"][0]["series"][0]["points"]
    assert points[0]["value"] is None
    assert points[0]["formula"] == "=100+10"


@pytest.mark.parametrize(
    "bad", ["#N/A Review: BQL Compute Capacity blocked", "#DIV/0!", "not numeric", None]
)
def test_invalid_values_unavailable(tmp_path, mapping, bad):
    snapshot = ExcelWorkbookProvider(tmp_path / "x.xlsx", mapping).read_bytes(
        workbook_bytes(value=bad)
    )
    points = snapshot["sections"]["Market Data"]["charts"][0]["series"][0]["points"]
    assert points[-1]["value"] is None
    assert snapshot["issues"]


def test_unit_and_layout_validation(tmp_path, mapping):
    provider = ExcelWorkbookProvider(tmp_path / "x.xlsx", mapping)
    with pytest.raises(ValueError, match="Unit/number format"):
        provider.read_bytes(workbook_bytes(unit="0%"))
    wrong = copy.deepcopy(mapping)
    wrong["sections"]["Market Data"]["tables"][0]["expected_headers"]["A1"] = "Wrong header"
    with pytest.raises(ValueError, match="Layout changed"):
        ExcelWorkbookProvider(tmp_path / "x.xlsx", wrong).read_bytes(workbook_bytes())
    wrong = copy.deepcopy(mapping)
    wrong["sections"]["Market Data"]["sheets"].append("Missing")
    with pytest.raises(ValueError, match="Missing mapped"):
        ExcelWorkbookProvider(tmp_path / "x.xlsx", wrong).read_bytes(workbook_bytes())


def test_range_and_date_validation(tmp_path, mapping):
    wrong = copy.deepcopy(mapping)
    wrong["sections"]["Market Data"]["charts"][0]["series"][0]["dates"] = "A2:A2"
    with pytest.raises(ValueError, match="range length mismatch"):
        ExcelWorkbookProvider(tmp_path / "x.xlsx", wrong).read_bytes(workbook_bytes())
    with pytest.raises(ValueError, match="observation date"):
        normalize_date(None, datetime(1899, 12, 30))
    assert normalize_date(45292, datetime(1899, 12, 30)) == "2024-01-01"


def test_atomic_import_failure_retains_snapshot(tmp_path, mapping):
    path = tmp_path / "master.xlsx"
    path.write_bytes(workbook_bytes())
    assert excel_sync.import_workbook(path, mapping) == "success"
    first = excel_sync.latest_import(True)
    assert excel_sync.import_workbook(path, mapping) == "unchanged"
    path.write_bytes(workbook_bytes(cached=None))
    assert excel_sync.import_workbook(path, mapping) == "failed"
    assert "Lost valid" in excel_sync.latest_import()["error"]
    assert excel_sync.latest_import(True)["id"] == first["id"]
    path.write_bytes(b"incomplete zip save")
    assert excel_sync.import_workbook(path, mapping) == "failed"
    assert excel_sync.latest_import(True)["id"] == first["id"]
    path.write_bytes(workbook_bytes(value=140))
    assert excel_sync.import_workbook(path, mapping) == "success"
    assert excel_sync.latest_import(True)["id"] > first["id"]


def test_snapshot_persists_missing_as_null(tmp_path, mapping):
    path = tmp_path / "master.xlsx"
    path.write_bytes(workbook_bytes(cached=None))
    assert excel_sync.import_workbook(path, mapping) == "success"
    snapshot = excel_sync.latest_import(True)["snapshot"]
    assert "NaN" not in json.dumps(snapshot, allow_nan=False)


def test_poll_waits_and_hash_detects_same_stat_changes(tmp_path, monkeypatch):
    from src.settings import settings

    path = tmp_path / "master.xlsx"
    path.write_bytes(b"first")
    monkeypatch.setattr(settings, "excel_workbook_path", str(path))
    monkeypatch.setattr(settings, "excel_settle_seconds", 5)
    monkeypatch.setattr(excel_sync, "_candidate", None)
    monkeypatch.setattr(excel_sync, "_future", None)
    monkeypatch.setattr(excel_sync, "_attempted", None)
    monkeypatch.setattr(excel_sync, "_force_requested", False)
    now = [0.0]
    monkeypatch.setattr(excel_sync.time, "monotonic", lambda: now[0])
    submitted = []

    class Pool:
        def submit(self, function, path, **kwargs):
            submitted.append(path.read_bytes())

    monkeypatch.setattr(excel_sync, "_pool", Pool())
    assert "waiting" in excel_sync.poll_workbook(force=True).lower()
    now[0] = 4
    excel_sync.poll_workbook()
    assert not submitted
    now[0] = 6
    excel_sync.poll_workbook()
    assert submitted == [b"first"]
    import os

    stat = path.stat()
    path.write_bytes(b"other")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    excel_sync.poll_workbook()
    assert submitted[-1] == b"other"


def test_dashboard_uses_snapshot_and_updates(tmp_path, mapping, monkeypatch):
    from streamlit.testing.v1 import AppTest

    import dashboard.excel_views as views

    path = tmp_path / "master.xlsx"
    path.write_bytes(workbook_bytes())
    monkeypatch.setattr(views, "load_mapping", lambda: mapping)
    assert excel_sync.import_workbook(path, mapping) == "success"
    app = AppTest.from_string(
        "from dashboard.excel_views import render_section\nrender_section('Market Data')"
    ).run()
    assert not app.exception
    assert len(app.get("plotly_chart")) == 1
    original = app.get("plotly_chart")[0].proto.spec
    path.write_bytes(workbook_bytes(value=150))
    assert excel_sync.import_workbook(path, mapping) == "success"
    app.run()
    assert not app.exception
    assert app.get("plotly_chart")[0].proto.spec != original


def test_admin_page_without_workbook():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_string(
        "from dashboard.excel_views import render_administration\nrender_administration()"
    ).run()
    assert not app.exception
    assert app.button[0].label == "Reimport Workbook"
    assert app.button[0].disabled


def test_sponsor_mapping_contracts():
    from openpyxl.utils.cell import range_boundaries

    from src.providers.excel import load_mapping

    mapping = load_mapping()
    ids = []
    for section in mapping["sections"].values():
        for chart in section["charts"]:
            for spec in chart["series"]:
                x1, y1, x2, y2 = range_boundaries(spec["values"])
                a1, b1, a2, b2 = range_boundaries(spec["dates"])
                assert (x2 - x1 + 1) * (y2 - y1 + 1) == (a2 - a1 + 1) * (b2 - b1 + 1)
                assert spec["unit"] and spec["value_type"] == "number"
                ids.append(spec["id"])
    assert len(ids) == len(set(ids))
    housing = mapping["sections"]["Housing"]["charts"][0]["series"][1]
    assert housing["dates"] == "AC24:AC344"  # Own monthly dates, not quarterly affordability dates.


def test_selected_calculation_comparison():
    from src.analytics.excel_comparison import compare_calculations

    values = {
        ("BTC", "D4"): 100,
        ("BTC", "D5"): 20000,
        ("BTC", "D6"): 2,
        ("BTC", "D8"): 1,
        ("BTC", "D9"): 0.5,
        ("BTC", "D10"): 2,
    }
    checks = compare_calculations(lambda sheet, cell: values.get((sheet, cell)))
    assert all(c["status"] == "match" for c in checks[:3])
    values[("BTC", "D6")] = 20
    checks = compare_calculations(lambda sheet, cell: values.get((sheet, cell)))
    assert checks[0]["status"] == "mismatch"


def test_reported_quarter_marker_may_move_without_data_loss():
    old = {
        "sections": {
            "Demand": {
                "tables": [],
                "charts": [
                    {
                        "series": [
                            {
                                "id": "marker",
                                "role": "reported_marker",
                                "points": [{"date": "2024-03-31", "value": 1}],
                            }
                        ]
                    }
                ],
            }
        }
    }
    new = copy.deepcopy(old)
    new["sections"]["Demand"]["charts"][0]["series"][0]["points"] = [
        {"date": "2024-03-31", "value": None},
        {"date": "2024-06-30", "value": 1},
    ]
    excel_sync.validate_continuity(old, new)


def test_source_change_during_validation_is_not_published(tmp_path, mapping, monkeypatch):
    path = tmp_path / "master.xlsx"
    path.write_bytes(workbook_bytes())
    assert excel_sync.import_workbook(path, mapping) == "success"
    valid = excel_sync.latest_import(True)["id"]
    original = ExcelWorkbookProvider.read

    def change_after_read(provider):
        snapshot = original(provider)
        path.write_bytes(workbook_bytes(value=175))
        return snapshot

    monkeypatch.setattr(ExcelWorkbookProvider, "read", change_after_read)
    assert excel_sync.import_workbook(path, mapping, force=True) == "failed"
    assert "changed during validation" in excel_sync.latest_import()["error"]
    assert excel_sync.latest_import(True)["id"] == valid
