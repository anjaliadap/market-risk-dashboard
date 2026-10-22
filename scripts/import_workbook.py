"""Import or watch a configured local workbook; leave the source unchanged."""

import argparse
import logging
import time

from src.database.store import initialize
from src.excel_sync import poll_workbook, wait_and_import
from src.settings import settings

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=settings.excel_workbook_path)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not args.path:
        parser.error("Set EXCEL_WORKBOOK_PATH or provide a local workbook path")
    settings.excel_workbook_path = args.path
    logging.basicConfig(level=logging.INFO)
    initialize()
    if args.watch:
        while True:
            print(poll_workbook(), flush=True)
            time.sleep(max(1, settings.excel_poll_seconds))
    else:
        result = wait_and_import(args.path, force=args.force)
        print(result)
        raise SystemExit(1 if result == "failed" else 0)
