"""Refresh the three workbook sections, returning nonzero on any source failure."""

import argparse
import logging

from src.database.store import initialize
from src.providers.workbook_sections import SECTION_IDS, group_key
from src.refresh import due, refresh_one


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--due-only", action="store_true", help="Respect source refresh intervals")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    initialize()
    keys = list(dict.fromkeys(group_key(key) for key in SECTION_IDS))
    results = [refresh_one(key) for key in keys if not args.due_only or due(key)]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
