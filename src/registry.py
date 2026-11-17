import json
from pathlib import Path

REGISTRY = json.loads((Path(__file__).resolve().parents[1] / "config/series.json").read_text())
REGISTRY += json.loads(
    (Path(__file__).resolve().parents[1] / "config/workbook_series.json").read_text()
)
BY_ID = {s["id"]: s for s in REGISTRY}
if len(BY_ID) != len(REGISTRY):
    raise ValueError("Duplicate source registry identifier")
