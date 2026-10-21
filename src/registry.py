import json
from pathlib import Path

REGISTRY = json.loads((Path(__file__).resolve().parents[1] / "config/series.json").read_text())
BY_ID = {s["id"]: s for s in REGISTRY}
