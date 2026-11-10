"""Where the dashboard gets its data: SQLite for history, the gateway's /status for the live state."""
import sqlite3
from datetime import datetime

import pandas as pd
import requests

from gateway import settings
from detection import rules

CFG = settings.load()
GATEWAY = f"http://127.0.0.1:{CFG['gateway']['port']}"
TZ = datetime.now().astimezone().tzinfo


def _read(sql, args=()):
    try:
        con = sqlite3.connect(str(settings.resolve(CFG["gateway"]["db_path"])), timeout=5)
        try:
            return pd.read_sql_query(sql, con, params=args)
        finally:
            con.close()
    except (sqlite3.Error, pd.errors.DatabaseError):
        return pd.DataFrame()


def _local(ts):
    return pd.to_datetime(ts, unit="s", utc=True).dt.tz_convert(TZ).dt.tz_localize(None)


def status():
    try:
        return requests.get(f"{GATEWAY}/status", timeout=1.5).json()
    except (requests.RequestException, ValueError):
        return None


def telemetry(minutes=3):
    df = _read("select * from telemetry where arrival_ts > strftime('%s','now') - ? order by arrival_ts", (minutes * 60,))
    if df.empty:
        return df
    df["t"] = _local(df["arrival_ts"])
    return df


def events(limit=300):
    df = _read("select * from events order by ts desc limit ?", (limit,))
    if not df.empty:
        df["time"] = _local(df["ts"])
    return df


def experiments(limit=50):
    df = _read("select e.id, e.name, e.scenario, e.started, e.ended, e.node, e.field,"
               " (select count(*) from telemetry t where t.experiment_id = e.id) as samples"
               " from experiments e order by e.id desc limit ?", (limit,))
    if df.empty:
        return df
    df["running"] = df["ended"].isna()
    df["started"] = _local(df["started"])
    return df.drop(columns=["ended"])


def baseline():
    return rules.load_baseline(settings.resolve(CFG["gateway"]["baseline_path"]))


def send(path, payload=None):
    try:
        r = requests.post(f"{GATEWAY}{path}", json=payload or {}, timeout=2)
        return r.ok, (r.json() if r.ok else r.text)
    except requests.RequestException as err:
        return False, str(err)
