"""Writes the telemetry, events and experiments tables to CSV files (for the report and the viva)."""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gateway import settings  # noqa: E402


def main():
    cfg = settings.load()
    out = ROOT / "data" / "exports"
    out.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(settings.resolve(cfg["gateway"]["db_path"])))
    for table in ("telemetry", "events", "experiments"):
        df = pd.read_sql_query(f"select * from {table}", con)
        df.to_csv(out / f"{table}.csv", index=False)
        print(f"{table}: {len(df)} rows")
    con.close()
    print("saved in", out)


if __name__ == "__main__":
    main()
