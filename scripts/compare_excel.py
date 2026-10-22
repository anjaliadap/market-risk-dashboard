"""Compare selected Python calculations against saved Excel outputs, without recalculation."""

import argparse
import json
from pathlib import Path

from openpyxl import load_workbook

from src.analytics.excel_comparison import compare_calculations
from src.settings import settings

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=settings.excel_workbook_path)
    args = parser.parse_args()
    if not args.path:
        parser.error("Set EXCEL_WORKBOOK_PATH or provide the local workbook path")
    workbook = load_workbook(args.path, data_only=True, read_only=True)
    try:
        results = compare_calculations(lambda sheet, cell: workbook[sheet][cell].value)
    finally:
        workbook.close()
    folder = Path(settings.excel_artifact_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "excel_comparison.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    for check in results:
        print(check["status"], check["calculation"])
    raise SystemExit(0 if all(c["status"] == "match" for c in results) else 1)
