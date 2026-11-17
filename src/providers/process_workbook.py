"""Read the updated Process workbook. No network calls or Excel formula execution.

Proprietary/manual readings retain their saved values. Only the explicitly defined
Gold/Brent arithmetic and calendar changes are calculated from the same workbook.
"""

import hashlib
import json
import math
import re
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.cell import column_index_from_string

from src.providers.excel import is_error, normalize_date

MAPPING_PATH = Path(__file__).resolve().parents[2] / "config/process_sections.json"


def load_process_mapping():
    return json.loads(MAPPING_PATH.read_text(encoding="utf-8"))


def _month_key(value, months=0):
    year, month = map(int, value[:7].split("-"))
    offset = year * 12 + month - 1 - months
    return f"{offset // 12:04d}-{offset % 12 + 1:02d}"


def _change(values, current_date, months):
    current = values.get(_month_key(current_date))
    previous = values.get(_month_key(current_date, months))
    return current - previous if current is not None and previous is not None else None


class ProcessWorkbookProvider:
    def __init__(self, path, mapping=None):
        self.path = Path(path).expanduser().resolve()
        self.mapping = mapping if mapping is not None else load_process_mapping()

    def read(self):
        before = self.path.stat()
        blob = self.path.read_bytes()
        after = self.path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Workbook changed during read; wait for Excel save to finish")
        return self.read_bytes(blob, after.st_mtime)

    def read_bytes(self, blob, modified_at=None):
        formulas = load_workbook(BytesIO(blob), data_only=False, keep_links=True)
        cached = load_workbook(BytesIO(blob), data_only=True, keep_links=True)
        self.formulas, self.cached = formulas, cached
        self.issues = []
        self.diagnostics = {"missing_saved_values": 0, "source_calculation_mismatches": 0}
        try:
            for spec in self.mapping["sections"].values():
                if spec["sheet"] not in cached.sheetnames:
                    raise ValueError(f"Missing Process worksheet: {spec['sheet']}")
                for cell, label in spec.get("headers", {}).items():
                    if cached[spec["sheet"]][cell].value != label:
                        raise ValueError(f"Layout changed: {spec['sheet']}!{cell}")
            sections = {
                "Gold to Oil": self._gold(),
                "Intra-Sector Spread": self._intra(),
                "Trend Following": self._trend(),
                "NDR": self._ndr(),
            }
            latest = max(
                [p["date"] for p in sections["Gold to Oil"]["history"] if not p["is_current"]]
                + sections["Intra-Sector Spread"]["dates"]
                + [p["date"] for p in sections["Trend Following"]["history"]],
                default=None,
            )
            metric_count = (
                sum(p["percentile"] is not None for p in sections["Intra-Sector Spread"]["history"])
                + sum(p["quintile"] is not None for p in sections["Trend Following"]["history"])
                + sum(p["ratio"] is not None for p in sections["Gold to Oil"]["history"])
                + sum(
                    r["annualized_return"] is not None
                    for g in sections["NDR"]["groups"]
                    for r in g["rows"]
                )
            )
            if not metric_count:
                raise ValueError("No valid numeric inputs in the Process workbook")
            return {
                "profile": "process",
                "sha256": hashlib.sha256(blob).hexdigest(),
                "mapping_sha256": hashlib.sha256(
                    json.dumps(self.mapping, sort_keys=True).encode()
                ).hexdigest(),
                "path": str(self.path),
                "modified_at": modified_at,
                "sections": sections,
                "latest_observation": latest,
                "metric_count": metric_count,
                "diagnostics": self.diagnostics,
                "issues": self.issues,
                "refresh_attestation": "Saved workbook only; Bloomberg and manual update times are unverified",
            }
        finally:
            formulas.close()
            cached.close()

    def _issue(self, sheet, cell, reason, mismatch=False):
        self.issues.append(
            {
                "sheet": sheet,
                "cell": cell,
                "reason": reason,
                "kind": "calculation_mismatch" if mismatch else "missing_input",
            }
        )
        key = "source_calculation_mismatches" if mismatch else "missing_saved_values"
        self.diagnostics[key] += 1

    def _value(self, sheet, coordinate):
        cell = self.cached[sheet][coordinate]
        value = cell.value
        if cell.data_type == "e" or is_error(value):
            self._issue(sheet, coordinate, "Excel/Bloomberg error; saved value is unavailable")
            return None
        if value is None and self.formulas[sheet][coordinate].data_type == "f":
            self._issue(
                sheet, coordinate, "Formula has no saved value; refresh, calculate and save Excel"
            )
        return value

    def _number(self, sheet, coordinate, minimum=None, maximum=None, integer=False):
        value = self._value(sheet, coordinate)
        if value is None:
            if (
                self.cached[sheet][coordinate].value is None
                and self.formulas[sheet][coordinate].data_type != "f"
            ):
                self._issue(sheet, coordinate, "No saved input; value remains unavailable")
            return None
        valid = (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(value)
            and (minimum is None or value >= minimum)
            and (maximum is None or value <= maximum)
            and (not integer or value == int(value))
        )
        if not valid:
            self._issue(
                sheet, coordinate, "Saved number is nonnumeric or outside the source unit range"
            )
            return None
        return int(value) if integer else float(value)

    def _check(self, sheet, cell, expected, reason):
        if self.cached[sheet][cell].value is None and self.formulas[sheet][cell].data_type != "f":
            return
        saved = self._number(sheet, cell)
        if (
            saved is not None
            and expected is not None
            and not math.isclose(saved, expected, rel_tol=1e-9, abs_tol=1e-8)
        ):
            self._issue(sheet, cell, reason, mismatch=True)

    def _gold(self):
        spec = self.mapping["sections"]["Gold to Oil"]
        name, sheet = spec["sheet"], self.cached[spec["sheet"]]
        history, seen, current_rows = [], set(), []
        for row in range(spec["first_row"], sheet.max_row + 1):
            raw_date = self._value(name, f"{spec['gold_date_column']}{row}")
            if raw_date is None:
                if sheet[f"C{row}"].value is not None or sheet[f"F{row}"].value is not None:
                    raise ValueError(f"Missing Gold/Brent reference date: {name}!B{row}")
                continue
            observed = normalize_date(raw_date, self.cached.epoch)
            oil_date = normalize_date(
                self._value(name, f"{spec['oil_date_column']}{row}"), self.cached.epoch
            )
            if observed != oil_date:
                raise ValueError(f"Gold and Brent dates do not match: {name}!row {row}")
            if observed in seen:
                raise ValueError(f"Duplicate Gold/Brent date: {observed}")
            seen.add(observed)
            gold = self._number(name, f"{spec['gold_column']}{row}", minimum=1e-12)
            oil = self._number(name, f"{spec['oil_column']}{row}", minimum=1e-12)
            ratio = gold / oil if gold is not None and oil is not None else None
            current = (
                str(sheet[f"{spec['current_marker_column']}{row}"].value or "").strip().lower()
                == "current"
            )
            if current:
                current_rows.append(row)
            history.append(
                {
                    "date": observed,
                    "gold": gold,
                    "oil": oil,
                    "ratio": ratio,
                    "is_current": current,
                    "source_row": row,
                }
            )
            for column, expected in (("I", gold), ("J", oil), ("K", ratio)):
                self._check(
                    name,
                    f"{column}{row}",
                    expected,
                    "Saved calculation differs from same-date source prices; derived from workbook inputs",
                )
        if len(current_rows) != 1 or not history:
            raise ValueError("Gold to Oil needs exactly one Current row and dated source history")
        history.sort(key=lambda point: point["date"])
        current = next(point for point in history if point["is_current"])
        if current["date"] != history[-1]["date"]:
            raise ValueError("Gold to Oil Current row precedes historical observations")
        formula = self.formulas[name][spec["average_cell"]].value
        match = re.fullmatch(r"=AVERAGE\(\$?K\$?(\d+):\$?K\$?(\d+)\)", str(formula), re.IGNORECASE)
        if not match:
            raise ValueError("Gold to Oil averaging definition changed; review the Process mapping")
        first, last = map(int, match.groups())
        population = [p for p in history if first <= p["source_row"] <= last]
        if not population:
            raise ValueError("Gold to Oil averaging range contains no dated prices")
        # A missing input makes the average unavailable, rather than silently
        # shortening the sponsor's averaging population.
        average = (
            math.fsum(p["ratio"] for p in population) / len(population)
            if all(p["ratio"] is not None for p in population)
            else None
        )
        self._check(
            name,
            spec["average_cell"],
            average,
            "Saved long-term average differs from its defined workbook population",
        )
        for point in history:
            point["average"] = average
        current = {**current, "average": average}
        gold, oil = current["gold"], current["oil"]
        implied_gold = average * oil if average is not None and oil is not None else None
        implied_oil = gold / average if gold is not None and average else None
        gold_change = implied_gold / gold - 1 if implied_gold is not None and gold else None
        oil_change = implied_oil / oil - 1 if implied_oil is not None and oil else None
        controls = {
            "X7": oil,
            "X8": average,
            "X9": implied_gold,
            "X10": gold,
            "X11": gold_change,
            "X14": gold,
            "X15": average,
            "X16": implied_oil,
            "X17": oil,
            "X18": oil_change,
            "Q23": implied_gold,
            "Q24": gold,
            "Q25": gold_change,
            "Q27": implied_oil,
            "Q28": oil,
            "Q29": oil_change,
        }
        for cell, expected in controls.items():
            self._check(
                name,
                cell,
                expected,
                "Saved summary disagrees with same-date workbook inputs; panel recalculated using documented arithmetic",
            )
        display_formula = re.sub(r"[\s()]", "", str(self.formulas[name]["Q23"].value)).upper()
        if display_formula == "=X9-X9" and sheet["Q23"].value not in (None, 0):
            self._issue(
                name,
                "Q23",
                "The saved formula subtracts X9 from itself but its cache is nonzero; panel uses validated workbook-input arithmetic",
                mismatch=True,
            )
        return {
            "sheet": name,
            "history": history,
            "current": current,
            "implied": [
                {"asset": "Gold", "current": gold, "implied": implied_gold, "change": gold_change},
                {
                    "asset": "Brent futures",
                    "current": oil,
                    "implied": implied_oil,
                    "change": oil_change,
                },
            ],
            "notes": [
                "Gold: XAUUSD Curncy, USD per troy ounce. Brent: CO1 Comdty front-month futures, USD per barrel.",
                "The long-term mean follows the saved AVERAGE(K...) definition and includes the Current row when inside that range.",
                "Current is the workbook's saved reference date, not a verified quote timestamp. Refresh Bloomberg and save in Excel to update.",
                "Implied gold = mean ratio × Brent; implied Brent = gold ÷ mean ratio; change = implied ÷ current − 1.",
            ],
        }

    def _month_columns(self, sheet, spec, yyyymm=False):
        result, previous = [], None
        first = column_index_from_string(spec["first_column"])
        summary_row = spec["value_row"] - 1 if yyyymm else spec["date_row"]
        summary_labels = {"M/M", "Trailing 3M", "Trailing 6M", "Trailing 12M", "Sector", "Average"}
        boundary = next(
            (
                c.column
                for c in sheet[summary_row]
                if c.column >= first and c.value in summary_labels
            ),
            sheet.max_column + 1,
        )
        gap = False
        for column in range(first, boundary):
            value = sheet.cell(spec["date_row"], column).value
            if value is None:
                gap = True
                continue
            if gap:
                raise ValueError(
                    f"Missing internal date header in {sheet.title} before column {column}"
                )
            if yyyymm:
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise ValueError(f"Invalid YYYYMM month in {sheet.title}: {value}")
                if not math.isfinite(value) or int(value) != value or not 100001 <= value <= 999912:
                    raise ValueError(
                        f"Invalid YYYYMM month: {sheet.title}!{sheet.cell(spec['date_row'], column).coordinate}"
                    )
                year, month = divmod(int(value), 100)
                observed = date(year, month, 1).isoformat()
            else:
                if not isinstance(value, (date, datetime)):
                    raise ValueError(f"Invalid monthly date header in {sheet.title}: {value}")
                observed = normalize_date(value, self.cached.epoch)
            key = _month_key(observed)
            if previous is not None and key <= previous:
                raise ValueError(f"Duplicate or out-of-order month in {sheet.title}: {key}")
            previous = key
            result.append((column, observed))
        if not result:
            raise ValueError(f"No monthly observations in {sheet.title}")
        return result

    def _intra(self):
        spec = self.mapping["sections"]["Intra-Sector Spread"]
        name, sheet = spec["sheet"], self.cached[spec["sheet"]]
        columns = self._month_columns(sheet, spec)
        sectors = [
            sheet[f"{spec['sector_column']}{r}"].value
            for r in range(spec["first_row"], spec["last_row"] + 1)
        ]
        if sectors != spec["sectors"]:
            raise ValueError(
                "Intra-Sector Spreads category labels changed; review the Process mapping"
            )
        averages = [c.column for c in sheet[spec["date_row"]] if c.value == "Average"]
        if len(averages) != 1:
            raise ValueError(
                "Intra-Sector Spreads Average reference column is missing or ambiguous"
            )
        history, current = [], []
        for row, sector in zip(
            range(spec["first_row"], spec["last_row"] + 1), sectors, strict=True
        ):
            values = {}
            for column, observed in columns:
                cell = sheet.cell(row, column).coordinate
                value = self._number(name, cell, minimum=0, maximum=100)
                values[_month_key(observed)] = value
                history.append(
                    {"date": observed, "sector": sector, "percentile": value, "cell": cell}
                )
            observed = columns[-1][1]
            average = self._number(
                name, sheet.cell(row, averages[0]).coordinate, minimum=0, maximum=100
            )
            current.append(
                {
                    "sector": sector,
                    "percentile": values[_month_key(observed)],
                    "average": average,
                    **{f"change_{m}m": _change(values, observed, m) for m in (1, 3, 6, 12)},
                }
            )
            self._check_changes(sheet, spec["date_row"], row, current[-1])
            summary = next((c.column for c in sheet[spec["date_row"]] if c.value == "Sector"), None)
            if summary is not None:
                self._check(
                    name,
                    sheet.cell(row, summary + 1).coordinate,
                    current[-1]["percentile"],
                    "Saved current-percentile summary does not match the latest monthly input",
                )
        return {
            "sheet": name,
            "dates": [d for _, d in columns],
            "history": history,
            "current": current,
            "as_of": columns[-1][1],
            "notes": [
                "Manually updated monthly. Percentiles are the supplied historical rankings; the dashboard does not recreate the proprietary model.",
                "Historical ranking window is supplied as 1952–current; this file's saved observation history starts later. Hidden source columns are included. Blanks remain gaps.",
                "Changes are percentile-point differences to exact calendar months, not percentage returns.",
            ],
        }

    def _trend(self):
        spec = self.mapping["sections"]["Trend Following"]
        name, sheet = spec["sheet"], self.cached[spec["sheet"]]
        columns = self._month_columns(sheet, spec, yyyymm=True)
        history = [
            {
                "date": observed,
                "quintile": self._number(
                    name,
                    sheet.cell(spec["value_row"], column).coordinate,
                    minimum=1,
                    maximum=5,
                    integer=True,
                ),
                "cell": sheet.cell(spec["value_row"], column).coordinate,
            }
            for column, observed in columns
        ]
        values = {_month_key(p["date"]): p["quintile"] for p in history}
        # Insert explicit nulls for skipped months so the filled step chart does
        # not carry a regime across an unobserved interval.
        by_month = {_month_key(p["date"]): p for p in history}
        first_year, first_month = map(int, history[0]["date"][:7].split("-"))
        last_year, last_month = map(int, history[-1]["date"][:7].split("-"))
        history = []
        for month in range(first_year * 12 + first_month - 1, last_year * 12 + last_month):
            key = f"{month // 12:04d}-{month % 12 + 1:02d}"
            history.append(by_month.get(key, {"date": key + "-01", "quintile": None, "cell": None}))
        current = {
            **history[-1],
            **{f"change_{m}m": _change(values, history[-1]["date"], m) for m in (1, 3, 6, 12)},
        }
        self._check_changes(sheet, spec["value_row"] - 1, spec["value_row"], current)
        return {
            "sheet": name,
            "history": history,
            "current": current,
            "notes": [
                "Supplied Trend Following Indicator 2.0 monthly quintiles. Five is most favorable for trend following, one least favorable.",
                "Manually updated in the workbook. No indicator model or public substitute is calculated. Changes are quintile points.",
            ],
        }

    def _check_changes(self, sheet, header_row, value_row, current):
        for label, months in (
            ("M/M", 1),
            ("Trailing 3M", 3),
            ("Trailing 6M", 6),
            ("Trailing 12M", 12),
        ):
            headers = [c.column for c in sheet[header_row] if c.value == label]
            if len(headers) > 1:
                raise ValueError(f"Ambiguous change header in {sheet.title}: {label}")
            if headers:
                self._check(
                    sheet.title,
                    sheet.cell(value_row, headers[0]).coordinate,
                    current[f"change_{months}m"],
                    "Saved change helper differs from exact-calendar-month input differences",
                )

    def _ndr(self):
        spec = self.mapping["sections"]["NDR"]
        name = spec["sheet"]
        groups = []
        for group in spec["groups"]:
            rows = []
            for row in group["rows"]:
                model = self._value(name, f"B{row}")
                if not isinstance(model, str) or model.strip() != spec["models"][str(row)]:
                    raise ValueError(f"NDR model layout changed: B{row}")
                reading = self._value(name, f"C{row}")
                rows.append(
                    {
                        "model": model.strip(),
                        "reading": reading,
                        "start_year": self._number(
                            name, f"E{row}", minimum=1800, maximum=2200, integer=True
                        ),
                        "annualized_return": self._number(name, f"D{row}"),
                        "return_kind": "next_year_median" if row == 10 else "annualized",
                        "source_row": row,
                        "code": self._value(name, f"G{row}"),
                        "source_note": self._value(name, f"H{row}"),
                        "external_link": "[" in str(self.formulas[name][f"D{row}"].value or ""),
                    }
                )
            groups.append({"name": group["name"], "rows": rows})
        warnings = []
        for warning in spec["warnings"]:
            row, threshold = warning["row"], warning["threshold"]
            model = self._value(name, f"B{row}")
            if not isinstance(model, str) or f">{threshold:.0%}" not in model:
                raise ValueError(f"NDR warning threshold label changed: B{row}")
            previous = self._number(name, f"D{row}", minimum=0, maximum=1)
            current = self._number(name, f"E{row}", minimum=0, maximum=1)
            warnings.append(
                {
                    "model": model,
                    "previous": previous,
                    "current": current,
                    "threshold": threshold,
                    "triggered": current > threshold if current is not None else None,
                }
            )
        return {
            "sheet": name,
            "groups": groups,
            "warnings": warnings,
            "as_of": None,
            "calculator": self._ndr_calculator(name),
            "notes": [
                "Manual model readings have no observation date in the source. The calculator's TODAY() value is not evidence of their update date.",
                "Returns and readings are retained from the workbook; conditional historical returns are descriptive, not dashboard forecasts.",
                "AAII Bull Less Bear return is a saved external-workbook link. Its reading is blank in the supplied file; it is not silently replaced by local AAII data.",
                "Warning rules use the source's strict greater-than thresholds. Equal-to-threshold does not trigger.",
            ],
        }

    def _ndr_calculator(self, name):
        sheet = self.cached[name]
        base = self._number(name, "K5", minimum=1e-12)
        gain = self._number(name, "D9", minimum=-1)
        price = self._number(name, "K8", minimum=1e-12)
        median = self._number(name, "D10", minimum=-1)
        self._check(
            name,
            "K6",
            self._number(name, "D9"),
            "Saved calculator gain link differs from the record-highs model row",
        )
        self._check(
            name,
            "K11",
            self._number(name, "D10"),
            "Saved calculator median-gain link differs from the supplied next-year median",
        )
        current_implied = base * (1 + gain) if base is not None and gain is not None else None
        next_implied = (
            current_implied * (1 + median)
            if current_implied is not None and median is not None
            else None
        )
        current_upside = (
            current_implied / price - 1 if current_implied is not None and price else None
        )
        next_upside = next_implied / price - 1 if next_implied is not None and price else None
        reference = self._value(name, "L12")
        target = self._value(name, "L13")
        reference = normalize_date(reference, self.cached.epoch) if reference is not None else None
        target = normalize_date(target, self.cached.epoch) if target is not None else None
        days = (
            (date.fromisoformat(target) - date.fromisoformat(reference)).days
            if reference and target
            else None
        )
        annualized = (
            (1 + next_upside) ** (365.25 / days) - 1
            if next_upside is not None and 1 + next_upside > 0 and days and days > 0
            else None
        )
        computed = {
            5: base,
            6: gain,
            7: current_implied,
            8: price,
            9: current_upside,
            11: median,
            12: next_implied,
            13: next_upside,
            14: annualized,
        }
        for row, value in computed.items():
            self._check(
                name,
                f"K{row}",
                value,
                "Saved record-highs calculator disagrees with its workbook assumptions",
            )
        self._check(name, "L14", days, "Saved calculator day count differs from its source dates")
        return {
            "rows": [
                {
                    "label": sheet[f"J{row}"].value,
                    "value": value,
                    "format": sheet[f"K{row}"].number_format,
                    "cell": f"K{row}",
                }
                for row, value in computed.items()
            ],
            "reference_date": reference,
            "target_date": target,
            "notes": [
                "Uses the workbook's supplied historical gain assumptions and scenario labels. These are arithmetic scenarios, not dashboard forecasts.",
                "Calculator reference date is not the update date of the manual NDR readings.",
            ],
        }


def validate_process_continuity(previous, current):
    """Reject lost valid history or fields; revisions may change numeric values."""
    if not previous:
        return

    def require(old, new, label):
        if old is not None and new is None:
            raise ValueError(f"Lost valid Process workbook value: {label}")

    for title, old in previous["sections"].items():
        if title not in current["sections"]:
            raise ValueError(f"Missing previously imported Process section: {title}")
        new = current["sections"][title]
        if "history" in old:
            keys = ("date", "sector") if title == "Intra-Sector Spread" else ("date",)
            indexed = {tuple(p[k] for k in keys): p for p in new["history"]}
            fields = {
                "Gold to Oil": ("gold", "oil", "ratio"),
                "Intra-Sector Spread": ("percentile",),
                "Trend Following": ("quintile",),
            }[title]
            for point in old["history"]:
                if point.get("is_current"):
                    continue  # Saved current quotes roll forward rather than become monthly history.
                key = tuple(point[k] for k in keys)
                for field in fields:
                    require(point[field], indexed.get(key, {}).get(field), f"{title} {key} {field}")
        if title in ("Gold to Oil", "Trend Following"):
            fields = (
                ("gold", "oil", "ratio", "average") if title == "Gold to Oil" else ("quintile",)
            )
            for field in fields:
                require(
                    old["current"].get(field), new["current"].get(field), f"{title} current {field}"
                )
        if title == "Intra-Sector Spread":
            indexed = {r["sector"]: r for r in new["current"]}
            for row in old["current"]:
                for field in ("percentile", "average"):
                    require(
                        row.get(field),
                        indexed.get(row["sector"], {}).get(field),
                        f"{title} {row['sector']} {field}",
                    )
        if title == "NDR":
            for field in ("reference_date", "target_date"):
                require(
                    old.get("calculator", {}).get(field),
                    new.get("calculator", {}).get(field),
                    f"NDR calculator {field}",
                )
            calculator = {
                r["cell"]: r for r in new.get("calculator", {}).get("rows", []) if r.get("cell")
            }
            for row in old.get("calculator", {}).get("rows", []):
                if row.get("cell"):
                    require(
                        row.get("value"),
                        calculator.get(row["cell"], {}).get("value"),
                        f"NDR calculator {row['cell']}",
                    )
            indexed = {r["model"]: r for g in new["groups"] for r in g["rows"]}
            for group in old["groups"]:
                for row in group["rows"]:
                    for field in ("reading", "annualized_return", "start_year"):
                        require(
                            row.get(field),
                            indexed.get(row["model"], {}).get(field),
                            f"NDR {row['model']} {field}",
                        )
            indexed = {r["model"]: r for r in new["warnings"]}
            for row in old["warnings"]:
                for field in ("previous", "current", "threshold"):
                    require(
                        row.get(field),
                        indexed.get(row["model"], {}).get(field),
                        f"NDR {row['model']} {field}",
                    )
