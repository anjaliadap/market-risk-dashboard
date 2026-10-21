import argparse
import logging

from src.database.store import initialize
from src.refresh import refresh_one
from src.registry import REGISTRY

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--series", nargs="*")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    initialize()
    ids = args.series or [s["id"] for s in REGISTRY if s["category"] in ["Recession", "Consumer"]]
    if not ids:
        print("No verified AI provider yet; see docs/data_coverage.md")
    results = [refresh_one(key) for key in ids]
    raise SystemExit(0 if all(results) else 1)
