"""Read saved Excel values. Never evaluate formulas or save the source workbook."""

import hashlib
import json
import math
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.cell import get_column_letter, range_boundaries
from openpyxl.utils.datetime import from_excel

from src.provenance import WorkbookTracer

MAPPING_PATH = Path(__file__).resolve().parents[2] / "config/excel_mapping.json"
# Bump when the snapshot gains fields, so an unchanged workbook is re-imported once.
# 2: per-series and per-table data sources (src/provenance.py).
# 3: workbook origins stored as stable keys (display names come from config/providers.json).
SNAPSHOT_SCHEMA = 3
ERROR_PREFIXES = (
    "#N/A",
    "#REF!",
    "#VALUE!",
    "#DIV/0!",
    "#NAME?",
    "#NUM!",
    "#SPILL!",
    "#CALC!",
    "#GETTING_DATA",
    "#N/A Request",
    "#BLOCKED!",
)


def load_mapping():
    return json.loads(MAPPING_PATH.read_text(encoding="utf-8"))


def is_error(value):
    return isinstance(value, str) and value.lstrip().startswith(ERROR_PREFIXES)


def normalize_date(value, epoch):
    if isinstance(value, bool) or value is None or is_error(value):
        raise ValueError("Missing or invalid observation date")
    if isinstance(value, (int, float)):
        if not math.isfinite(value) or not 1 <= value <= 100000:
            raise ValueError("Invalid Excel serial date")
        value = from_excel(value, epoch)
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return datetime.fromisoformat(value).date().isoformat()
    raise ValueError("Unsupported observation date")


def numeric(value, spec):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing, nonnumeric or nonfinite saved value")
    if "min" in spec and value < spec["min"]:
        raise ValueError("Value below configured unit bound")
    if "max" in spec and value > spec["max"]:
        raise ValueError("Value above configured unit bound")
    return float(value)


def range_cells(sheet, area):
    c1, r1, c2, r2 = range_boundaries(area)
    if c1 != c2 and r1 != r2:
        raise ValueError("Time-series ranges must be one row or one column")
    return [
        cell
        for row in sheet.iter_rows(min_row=r1, max_row=r2, min_col=c1, max_col=c2)
        for cell in row
    ]


def chart_cells(cached, spec):
    """Extend paired ranges only through contiguous valid source coordinates."""
    xs, ys = cached[spec["date_sheet"]], cached[spec["sheet"]]
    dates, values = range_cells(xs, spec["dates"]), range_cells(ys, spec["values"])
    if not spec.get("extend") or not dates or not values:
        return dates, values
    horizontal = dates[0].row == dates[-1].row and len(dates) > 1
    last_x, last_y = dates[-1], values[-1]
    limit = min(xs.max_column, ys.max_column) if horizontal else min(xs.max_row, ys.max_row)
    endpoint = last_x.column if horizontal else last_x.row
    for offset in range(1, limit - endpoint + 1):
        dc = (
            xs.cell(last_x.row, last_x.column + offset)
            if horizontal
            else xs.cell(last_x.row + offset, last_x.column)
        )
        vc = (
            ys.cell(last_y.row, last_y.column + offset)
            if horizontal
            else ys.cell(last_y.row + offset, last_y.column)
        )
        try:
            chart_coordinate(dc.value, spec, cached.epoch)
        except (ValueError, TypeError):
            break  # Never cross a header, blank separator or summary area.
        dates.append(dc)
        values.append(vc)
    return dates, values


def shift_columns(area, offset):
    c1, r1, c2, r2 = range_boundaries(area)
    start = f"{get_column_letter(c1 + offset)}{r1}"
    end = f"{get_column_letter(c2 + offset)}{r2}"
    return start if start == end else start + ":" + end


def resolve_table(table, sheet):
    """Follow a unique, verified summary header when monthly columns move it."""
    if not table.get("follow_header"):
        return table
    c1, r1, _, _ = range_boundaries(table["range"])
    expected = table.get("expected_headers", {})

    def matches(offset):
        return all(
            sheet[shift_columns(cell, offset)].value == label for cell, label in expected.items()
        )

    if matches(0):
        return table
    offsets = [
        column - c1
        for column in range(1, sheet.max_column + 1)
        if sheet.cell(r1, column).value == expected.get(f"{get_column_letter(c1)}{r1}")
        and matches(column - c1)
    ]
    if len(offsets) != 1:
        raise ValueError(f"Missing or ambiguous summary header: {table['sheet']} {table['id']}")
    offset = offsets[0]
    result = {
        **table,
        "range": shift_columns(table["range"], offset),
        "expected_headers": {
            shift_columns(cell, offset): label for cell, label in expected.items()
        },
    }
    result["display_columns"] = [
        (get_column_letter(range_boundaries(column + "1")[0] + offset), label)
        for column, label in table["display_columns"]
    ]
    result["heatmap_columns"] = [
        get_column_letter(range_boundaries(column + "1")[0] + offset)
        for column in table.get("heatmap_columns", [])
    ]
    return result


def chart_coordinate(value, spec, epoch):
    kind = spec.get("date_type", "excel_date")
    if kind == "number":
        return numeric(value, {})
    if kind == "year":
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value != int(value)
            or not 1900 <= value <= 2200
        ):
            raise ValueError("Invalid annual category")
        return str(int(value))
    if kind == "yyyymm":
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value != int(value)
        ):
            raise ValueError("Invalid YYYYMM date")
        year, month = divmod(int(value), 100)
        return date(year, month, 1).isoformat()
    return normalize_date(value, epoch)


class ExcelWorkbookProvider:
    def __init__(self, path, mapping=None):
        self.path = Path(path).expanduser().resolve()
        self.mapping = mapping if mapping is not None else load_mapping()

    def read(self):
        before = self.path.stat()
        blob = self.path.read_bytes()
        after = self.path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Workbook changed during read; wait for Excel save to finish")
        return self.read_bytes(blob, after.st_mtime)

    def read_bytes(self, blob, modified_at=None):
        # Both views come from the exact same immutable byte buffer.
        formulas = load_workbook(BytesIO(blob), data_only=False, keep_links=True)
        cached = load_workbook(BytesIO(blob), data_only=True, keep_links=True)
        try:
            return self._extract(formulas, cached, blob, modified_at)
        finally:
            formulas.close()
            cached.close()

    def _extract(self, formulas, cached, blob, modified_at):
        issues = []
        diagnostics = {"missing_formula_caches": 0, "failed_bloomberg_values": 0, "error_values": 0}

        def cell_value(sheet, coordinate):
            cell = cached[sheet][coordinate]
            formula = formulas[sheet][coordinate].data_type == "f"
            value = cell.value
            problem = None
            if formula and value is None:
                problem = "Formula has no saved cache"
            elif cell.data_type == "e" or is_error(value):
                problem = "Excel/Bloomberg error in saved value"
            if problem:
                issues.append({"sheet": sheet, "cell": coordinate, "reason": problem})
                value = None
            return value, formula

        required_sheets = {
            s for section in self.mapping["sections"].values() for s in section["sheets"]
        }
        for name in sorted(required_sheets & set(cached.sheetnames)):
            for row in formulas[name]:
                for cell in row:
                    val = cached[name][cell.coordinate]
                    if cell.data_type == "f" and val.value is None:
                        diagnostics["missing_formula_caches"] += 1
                    if val.data_type == "e" or is_error(val.value):
                        diagnostics["error_values"] += 1
                        if cell.data_type == "f" or "BQL" in str(val.value):
                            diagnostics["failed_bloomberg_values"] += 1
        sections, rejected = {}, {}
        latest_dates = []
        metric_count = 0
        self._tracer = WorkbookTracer(formulas, cached)
        for section_name, config in self.mapping["sections"].items():
            # Each section is validated on its own: a tab whose layout, dates or units no longer
            # match its mapping is rejected whole (never partly shown) without blocking the rest.
            mark = (len(issues), len(latest_dates), metric_count)
            try:
                result = self._extract_section(
                    config, cached, formulas, cell_value, latest_dates, issues
                )
            except ValueError as exc:
                rejected[section_name] = str(exc)
                del issues[mark[0] :], latest_dates[mark[1] :]
                metric_count = mark[2]
                continue
            sections[section_name], count = result
            metric_count += count
        if not sections:
            reasons = "; ".join(f"{name}: {reason}" for name, reason in rejected.items())
            raise ValueError(f"No mapped section passed validation. {reasons}")
        if not metric_count:
            raise ValueError("No valid mapped numeric metrics in workbook")
        return {
            "sha256": hashlib.sha256(blob).hexdigest(),
            "mapping_sha256": hashlib.sha256(
                json.dumps(self.mapping, sort_keys=True).encode()
            ).hexdigest(),
            "path": str(self.path),
            "modified_at": modified_at,
            "sections": sections,
            "rejected_sections": rejected,
            "metric_count": metric_count,
            "latest_observation": max(latest_dates, default=None),
            "diagnostics": diagnostics,
            "issues": issues,
            "refresh_attestation": "Unknown: saved workbook caches do not attest Bloomberg refresh",
            "schema": SNAPSHOT_SCHEMA,
        }

    def _extract_section(self, config, cached, formulas, cell_value, latest_dates, issues):
        """One mapped section -> (section payload, numeric metric count). Raises ValueError."""
        missing = set(config["sheets"]) - set(cached.sheetnames)
        if missing:
            raise ValueError(f"Missing mapped worksheets: {', '.join(sorted(missing))}")
        metric_count = 0
        section = {"notes": config["notes"], "charts": [], "tables": []}
        for table in config["tables"]:
            table = resolve_table(table, cached[table["sheet"]])
            for coord, expected in table.get("expected_headers", {}).items():
                if cached[table["sheet"]][coord].value != expected:
                    raise ValueError(f"Layout changed: {table['sheet']}!{coord}")
            c1, r1, c2, r2 = range_boundaries(table["range"])
            extension = table.get("extend_columns")
            if extension:
                sheet = cached[table["sheet"]]
                for column in range(c2 + 1, sheet.max_column + 1):
                    year = sheet.cell(extension["header_row"], column).value
                    if not isinstance(year, (int, float)) or not 1900 <= year <= 2200:
                        break
                    c2 = column
            rows = []
            for row in cached[table["sheet"]].iter_rows(
                min_row=r1, max_row=r2, min_col=c1, max_col=c2
            ):
                output = []
                for cell in row:
                    value, formula = cell_value(table["sheet"], cell.coordinate)
                    if isinstance(value, float) and not math.isfinite(value):
                        issues.append(
                            {
                                "sheet": table["sheet"],
                                "cell": cell.coordinate,
                                "reason": "Nonfinite table value",
                            }
                        )
                        value = None
                    if isinstance(value, (date, datetime)):
                        value = value.isoformat()[:10]
                    output.append(
                        {
                            "cell": cell.coordinate,
                            "value": value,
                            "format": cell.number_format,
                            "formula": formula,
                            "font_color": str(
                                formulas[table["sheet"]][cell.coordinate].font.color.rgb
                            )
                            if formulas[table["sheet"]][cell.coordinate].font.color
                            and formulas[table["sheet"]][cell.coordinate].font.color.type == "rgb"
                            else None,
                        }
                    )
                rows.append(output)
            observed = None
            if table.get("date_cell"):
                value, _ = cell_value(table["sheet"], table["date_cell"])
                if value is not None:
                    observed = normalize_date(value, cached.epoch)
                    latest_dates.append(observed)
            if extension:
                display_columns = [
                    (
                        get_column_letter(column),
                        str(cached[table["sheet"]].cell(r1, column).value or "Metric"),
                    )
                    for column in range(c1, c2 + 1)
                ]
                table = {**table, "display_columns": display_columns}
            value_cells = [
                c["cell"]
                for row in rows
                for c in row
                if isinstance(c["value"], (int, float)) and not isinstance(c["value"], bool)
            ]
            section["tables"].append(
                {
                    **table,
                    "rows": rows,
                    "as_of": observed,
                    "sources": self._sources(table["sheet"], value_cells, sample=12),
                }
            )
            metric_count += sum(isinstance(c["value"], (int, float)) for row in rows for c in row)
        for chart in config["charts"]:
            chart_out = {"id": chart["id"], "title": chart["title"], "series": []}
            for spec in chart["series"]:
                if spec.get("name_cell"):
                    name = cached[spec["name_sheet"]][spec["name_cell"]].value
                    if name is not None and not is_error(name):
                        spec = {**spec, "name": str(name).replace("\n", " ")}
                if not spec.get("unit") or spec.get("value_type") != "number":
                    raise ValueError(f"Metric unit/type contract missing: {spec['id']}")
                dates, values = chart_cells(cached, spec)
                is_dated = spec.get("date_type") not in {"number", "year"}
                if len(dates) != len(values):
                    raise ValueError(f"Date/value range length mismatch: {spec['id']}")
                points, seen = [], set()
                reported_dates = []
                for dc, vc in zip(dates, values, strict=True):
                    d, _ = cell_value(spec["date_sheet"], dc.coordinate)
                    v, _ = cell_value(spec["sheet"], vc.coordinate)
                    if d is None and v is None:
                        continue  # Explicit chart ranges may contain trailing empty rows.
                    expected_format = spec.get("expected_number_format")
                    allowed_formats = spec.get("allowed_number_formats", [expected_format])
                    if (
                        v is not None
                        and expected_format
                        and spec.get("role") != "reported_marker"
                        and vc.number_format not in allowed_formats
                    ):
                        raise ValueError(
                            f"Unit/number format changed: {spec['sheet']}!{vc.coordinate}"
                        )
                    try:
                        normalized = chart_coordinate(d, spec, cached.epoch)
                    except ValueError as exc:
                        if self.mapping.get("version", 1) >= 2:
                            issues.append(
                                {
                                    "sheet": spec["date_sheet"],
                                    "cell": dc.coordinate,
                                    "reason": "Invalid chart coordinate; point unavailable",
                                }
                            )
                            continue
                        raise ValueError(
                            f"Invalid date {spec['date_sheet']}!{dc.coordinate}"
                        ) from exc
                    if is_dated and normalized in seen and not spec.get("allow_duplicate_dates"):
                        raise ValueError(f"Duplicate date in {spec['id']}: {normalized}")
                    seen.add(normalized)
                    try:
                        v = numeric(v, spec)
                    except ValueError as exc:
                        if spec.get("role") != "reported_marker":
                            issues.append(
                                {
                                    "sheet": spec["sheet"],
                                    "cell": vc.coordinate,
                                    "reason": str(exc),
                                }
                            )
                        v = None
                    forward = False
                    if spec.get("period_labels_row"):
                        label = (
                            cached[spec["date_sheet"]]
                            .cell(spec["period_labels_row"], dc.column)
                            .value
                        )
                        if not isinstance(label, str) or not any(
                            t in label for t in ("(Rep)", "(Fwd)")
                        ):
                            raise ValueError(
                                f"Missing reported/forward label for {spec['id']} {dc.coordinate}"
                            )
                        forward = "(Fwd)" in label
                        if not forward:
                            reported_dates.append(normalized)
                    if v is not None and not forward and is_dated:
                        latest_dates.append(normalized)
                    source_cell = formulas[spec["sheet"]][vc.coordinate]
                    formula = (
                        str(getattr(source_cell.value, "text", source_cell.value))
                        if source_cell.data_type == "f"
                        else None
                    )
                    points.append(
                        {
                            "date": normalized,
                            "value": v,
                            "cell": vc.coordinate,
                            "forward": forward,
                            "formula": formula,
                        }
                    )
                if is_dated:
                    points.sort(key=lambda p: p["date"])
                chart_out["series"].append(
                    {
                        **spec,
                        "points": points,
                        "latest_reported": max(reported_dates, default=None),
                        "sources": self._sources(
                            spec["sheet"], [p["cell"] for p in points if p["value"] is not None]
                        ),
                    }
                )
                if spec.get("role") != "reported_marker":
                    metric_count += any(p["value"] is not None for p in points)
            section["charts"].append(chart_out)
        return section, metric_count

    def _sources(self, sheet, coordinates, sample=5):
        """Origin of saved values (Bloomberg / manual / calculated). Never blocks an import."""
        try:
            return self._tracer.sources(sheet, coordinates, sample)
        # Labelling is descriptive; a tracing problem must not reject data.
        except (KeyError, ValueError, TypeError, AttributeError, IndexError, RecursionError):
            return []
