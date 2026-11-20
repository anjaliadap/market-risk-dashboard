"""Where each number came from: provider labels worked out from the data itself.

A *source* is a small dict ``{"provider", "detail", "via"}``, for example
``{"provider": "Bloomberg", "detail": "HOMECOMP Index PX_LAST", "via": "PCM - Monthly Market & Risk Monitor"}`` or
``{"provider": "FRED", "detail": "VIXCLS (producer: Cboe)", "via": ""}``. Sources travel with
pandas series in ``series.attrs["sources"]`` and with Plotly traces in ``trace.meta``, so the chart
caption always reflects the data actually plotted. Nothing here is hard-coded per page: downloaded
observations are labelled from the URL stored with them, and workbook values from how the saved
cell was produced (Bloomberg formula, manual input or workbook calculation).
"""

import json
import re
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from openpyxl.formula.tokenizer import Tokenizer, TokenizerError
from openpyxl.utils.cell import get_column_letter, range_boundaries

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config/providers.json"
MAX_DEPTH = 8
MAX_DETAILS = 4


@lru_cache(maxsize=1)
def config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def source(provider, detail="", via=""):
    return {"provider": provider, "detail": detail or "", "via": via or ""}


def _key(item):
    return (item["provider"], item["detail"], item["via"])


def merge(*groups):
    """Union of source lists, in first-seen order, without duplicates."""
    seen, out = set(), []
    for group in groups:
        for item in group or ():
            if _key(item) not in seen:
                seen.add(_key(item))
                out.append(dict(item))
    return out


# --- Independent downloads --------------------------------------------------------------------


def provider_for_url(url):
    """Provider label for a download URL; unknown sites are labelled by host name."""
    host = (urlparse(url or "").hostname or "").lower()
    if not host:
        return None
    for name, spec in config()["providers"].items():
        if any(host == d or host.endswith("." + d) for d in spec.get("domains", ())):
            return name
    return host.removeprefix("www.")


def producer(registry_entry):
    """Underlying producer named in a registry entry ("...; producer: BLS"), if any."""
    match = re.search(r"producer:\s*([^;]+)", (registry_entry or {}).get("source", ""))
    return match.group(1).strip() if match else None


def independent_sources(series_id, url, registry_entry=None):
    provider = provider_for_url(url) or "Unknown source"
    who = producer(registry_entry) if provider == "FRED" else None
    return [source(provider, f"{series_id} (producer: {who})" if who else series_id)]


# --- Pandas and Plotly carriers ---------------------------------------------------------------


def tag(series, sources):
    """Attach sources to a pandas object (returned for chaining)."""
    series.attrs["sources"] = merge(sources)
    return series


def sources_of(*objects):
    """Sources carried by pandas objects, traces or plain lists, merged."""
    groups = []
    for obj in objects:
        if obj is None:
            continue
        if isinstance(obj, list):
            groups.append(obj)
        elif hasattr(obj, "attrs"):
            groups.append(obj.attrs.get("sources"))
        elif isinstance(getattr(obj, "meta", None), dict):
            groups.append(obj.meta.get("sources"))
    return merge(*groups)


def carry(result, *inputs):
    """Label a derived series with the sources of every input.

    pandas keeps only the left operand's attrs in binary operations and drops them in rolling
    windows, so combined or smoothed series are re-labelled explicitly with this helper.
    """
    if hasattr(result, "attrs"):
        result.attrs["sources"] = sources_of(*inputs)
    return result


_PAGE = ContextVar("page_sources", default=None)


def reset_page():
    """Start a fresh record of the sources read while rendering one page."""
    _PAGE.set([])


def note_page(sources):
    current = _PAGE.get()
    if current is not None:
        _PAGE.set(merge(current, sources))


def page_sources():
    return list(_PAGE.get() or [])


# Workbook origins are stored as stable keys and given their display name only when shown, so
# renaming a label in config/providers.json applies to snapshots that were imported earlier.
WORKBOOK_KEYS = {
    "workbook:via": "via",
    "workbook:manual": "manual",
    "workbook:calculated": "calculated",
    "workbook:unknown": "unknown",
}
LEGACY_LABELS = {  # Display text stored by snapshots imported before keys were used.
    "sponsor workbook": "workbook:via",
    "Sponsor workbook": "workbook:unknown",
    "Sponsor workbook (manual input)": "workbook:manual",
    "Sponsor workbook (calculated)": "workbook:calculated",
}


def display(name):
    """Current display name for a provider or 'via' value (stable keys and legacy text)."""
    key = LEGACY_LABELS.get(name, name)
    if key in WORKBOOK_KEYS:
        return config()["workbook"][WORKBOOK_KEYS[key]]
    return name


def describe(sources):
    """'Bloomberg (HOMECOMP Index PX_LAST) via PCM - Monthly Market & Risk Monitor · FRED (VIXCLS)'."""
    groups = {}
    for item in sources or ():
        key = (display(item["provider"]), display(item["via"]) if item["via"] else "")
        groups.setdefault(key, []).append(item["detail"])
    parts = []
    for (provider, via), details in groups.items():
        details = [d for d in dict.fromkeys(details) if d]
        text = provider
        if details:
            shown = details[:MAX_DETAILS]
            more = len(details) - len(shown)
            text += " (" + "; ".join(shown) + (f"; +{more} more" if more else "") + ")"
        if via:
            text += f" via {via}"
        parts.append(text)
    return " · ".join(parts)


def providers(sources):
    return list(dict.fromkeys(display(item["provider"]) for item in sources or ()))


# --- Saved workbook ---------------------------------------------------------------------------

_ARGS = re.compile(r"(?:^|[^A-Za-z0-9_])({})\s*\(\s*([^,()]+)(?:\s*,\s*([^,()]+))?", re.IGNORECASE)
_SIZE = re.compile(r"(rows|cols)\s*=\s*(\d+)", re.IGNORECASE)


class WorkbookTracer:
    """Classify saved workbook cells by origin: Bloomberg, manual input or calculation.

    Formulas are followed back through cell references (sampled for ranges) to their inputs. A
    Bloomberg function anywhere upstream labels the value Bloomberg, with ticker and field. A
    numeric constant upstream is a manual input. Cells written by a Bloomberg BDH/BDS array
    (``cols=..;rows=..`` in the formula) count as Bloomberg even though they hold plain values.
    Dates and text are ignored, so lookup keys do not mark a value as manual.
    """

    def __init__(self, formulas, cached):
        self.formulas, self.cached = formulas, cached
        cfg = config()
        names = "|".join(cfg["providers"]["Bloomberg"]["formulas"])
        self.pattern = re.compile(_ARGS.pattern.format(names), re.IGNORECASE)
        self.via = "workbook:via"
        self.manual = source("workbook:manual")
        self.calculated = source("workbook:calculated")
        self.memo, self.spills = {}, {}

    # Bloomberg arrays ------------------------------------------------------------------------
    def _formula_text(self, cell):
        value = cell.value
        text = getattr(value, "text", value)
        if isinstance(text, str) and text.startswith("="):
            return text
        return None

    def _argument(self, sheet, raw):
        raw = (raw or "").strip()
        if len(raw) >= 2 and raw[0] == raw[-1] == '"':
            return raw[1:-1]
        try:
            target_sheet, area = self._split(raw, sheet)
            value = self.cached[target_sheet][area.replace("$", "")].value
            return str(value) if value is not None else ""
        except (KeyError, ValueError, AttributeError, TypeError):
            return ""

    def _bloomberg(self, sheet, text):
        match = self.pattern.search(text)
        if not match:
            return None
        ticker = self._argument(sheet, match.group(2))
        field = self._argument(sheet, match.group(3)) if match.group(3) else ""
        detail = " ".join(part for part in (ticker, field) if part)
        return source("Bloomberg", detail, self.via)

    def _spill_map(self, sheet):
        if sheet not in self.spills:
            regions = {}
            ws = self.formulas[sheet]
            for row in ws.iter_rows():
                for cell in row:
                    text = self._formula_text(cell)
                    if not text:
                        continue
                    found = self._bloomberg(sheet, text)
                    size = {k.lower(): int(v) for k, v in _SIZE.findall(text)}
                    if not found or "rows" not in size:
                        continue
                    for r in range(cell.row, cell.row + size["rows"]):
                        for c in range(cell.column, cell.column + size.get("cols", 1)):
                            regions[f"{get_column_letter(c)}{r}"] = found
            self.spills[sheet] = regions
        return self.spills[sheet]

    # References ------------------------------------------------------------------------------
    @staticmethod
    def _split(reference, sheet):
        if "!" in reference:
            target, area = reference.rsplit("!", 1)
            target = target.strip("'").replace("''", "'")
        else:
            target, area = sheet, reference
        if "[" in target:
            raise ValueError("External workbook reference")
        return target, area

    def _references(self, sheet, text):
        try:
            items = Tokenizer(text).items
        except (TokenizerError, ValueError, IndexError):
            return []
        cells = []
        for token in items:
            if token.type != "OPERAND" or token.subtype != "RANGE":
                continue
            try:
                target, area = self._split(token.value, sheet)
                if target not in self.formulas.sheetnames:
                    continue
                c1, r1, c2, r2 = range_boundaries(area.replace("$", ""))
            except (ValueError, TypeError):
                continue  # Defined names, whole columns and external links are not traced.
            if None in (c1, r1, c2, r2):
                continue
            rows = sorted({r1, (r1 + r2) // 2, r2})
            cols = sorted({c1, (c1 + c2) // 2, c2})
            cells.extend((target, f"{get_column_letter(c)}{r}") for r in rows for c in cols)
        return cells

    # Classification --------------------------------------------------------------------------
    def classify(self, sheet, coordinate, depth=0):
        key = (sheet, coordinate)
        if key in self.memo:
            return self.memo[key]
        self.memo[key] = []  # Guards against circular references.
        cell = self.formulas[sheet][coordinate]
        text = self._formula_text(cell)
        result = []
        if text:
            found = self._bloomberg(sheet, text)
            if found:
                result = [found]
            elif depth < MAX_DEPTH:
                upstream = [
                    self.classify(s, c, depth + 1) for s, c in self._references(sheet, text)
                ]
                result = merge(*upstream) or [self.calculated]
            else:
                result = [self.calculated]
        elif coordinate in self._spill_map(sheet):
            result = [self._spill_map(sheet)[coordinate]]
        elif isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
            result = [self.manual]
        self.memo[key] = result
        return result

    def sources(self, sheet, coordinates, sample=5):
        """Merged sources for a sample of value cells (first, last and evenly spaced)."""
        coordinates = list(coordinates)
        if not coordinates:
            return []
        step = max(1, len(coordinates) // max(1, sample - 1))
        picks = dict.fromkeys(coordinates[::step] + [coordinates[-1]])
        return merge(*(self.classify(sheet, c) for c in picks))
