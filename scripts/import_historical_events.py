import argparse
import json

import pandas as pd
from sqlalchemy.orm import Session

from src.database.store import ResearchRecord, engine, initialize

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    args = parser.parse_args()
    frame = pd.read_excel(args.file) if args.file.endswith(".xlsx") else pd.read_csv(args.file)
    if not {"name", "date", "kind"}.issubset(frame.columns):
        raise ValueError("Required columns: name,date,kind")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.strftime("%Y-%m-%d")
    if frame[["name", "date", "kind"]].isna().any().any():
        raise ValueError("Missing event fields")
    initialize()
    with Session(engine) as session, session.begin():
        for row in frame.to_dict("records"):
            session.add(
                ResearchRecord(kind="historical_event", name=row["name"], payload=json.dumps(row))
            )
    print(f"Imported {len(frame)} events; duplicate names/versions rejected transactionally")
