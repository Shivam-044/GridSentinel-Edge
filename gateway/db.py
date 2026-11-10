"""SQLite storage for telemetry, events, experiments and commands."""
import json
import sqlite3
import threading
import time

SCHEMA = """
create table if not exists telemetry (
    id integer primary key autoincrement,
    node_id text not null, seq integer, uptime_ms integer, arrival_ts real not null,
    bus_v real, current_a real, power_w real, vsense_v real,
    relay_on integer, rssi integer, fw text,
    seq_flag text, same integer default 0,
    injected integer default 0, raw text,
    scenario text, experiment_id integer
);
create index if not exists ix_telemetry_ts on telemetry (arrival_ts);
create index if not exists ix_telemetry_exp on telemetry (experiment_id);

create table if not exists events (
    id integer primary key autoincrement,
    ts real not null, experiment_id integer, scenario text,
    label text not null, source text, detail text, response text
);

create table if not exists experiments (
    id integer primary key autoincrement,
    name text, scenario text, started real, ended real,
    node text, field text, params text
);

create table if not exists commands (
    id integer primary key autoincrement,
    ts real, node_id text, command text, text text,
    state text default 'pending', acked_ts real
);
"""


class Store:
    def __init__(self, path):
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("pragma journal_mode=wal")
        self.conn.executescript(SCHEMA)
        self.lock = threading.Lock()

    def run(self, sql, args=()):
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur

    def query(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def add_telemetry(self, r):
        self.run(
            "insert into telemetry (node_id, seq, uptime_ms, arrival_ts, bus_v, current_a, power_w, vsense_v,"
            " relay_on, rssi, fw, seq_flag, same, injected, raw, scenario, experiment_id)"
            " values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r["node_id"], r["seq"], r["uptime_ms"], r["ts"], r["bus_v"], r["current_a"], r["power_w"],
             r.get("vsense_v"), None if r.get("relay_on") is None else int(r["relay_on"]), r.get("rssi"),
             r.get("fw"), r.get("seq_flag"), int(bool(r.get("same"))), int(bool(r.get("injected"))),
             r.get("raw"), r.get("scenario"), r.get("experiment_id")))

    def add_event(self, ts, label, source, detail, response, experiment_id=None, scenario=None):
        self.run("insert into events (ts, experiment_id, scenario, label, source, detail, response)"
                 " values (?,?,?,?,?,?,?)", (ts, experiment_id, scenario, label, source, json.dumps(detail), response))

    def start_experiment(self, name, scenario, node, field, params, now=None):
        cur = self.run("insert into experiments (name, scenario, started, node, field, params) values (?,?,?,?,?,?)",
                       (name, scenario, now or time.time(), node, field, json.dumps(params)))
        return cur.lastrowid

    def end_experiment(self, exp_id, now=None):
        self.run("update experiments set ended=? where id=?", (now or time.time(), exp_id))

    def queue_command(self, node_id, command, text="", now=None):
        cur = self.run("insert into commands (ts, node_id, command, text) values (?,?,?,?)",
                       (now or time.time(), node_id, command, text))
        return cur.lastrowid

    def next_command(self, node_id):
        """Oldest pending command for a node. It is marked as sent so it only runs once."""
        rows = self.query("select id, command, text from commands where node_id=? and state='pending'"
                          " order by id limit 1", (node_id,))
        if not rows:
            return None
        self.run("update commands set state='sent' where id=?", (rows[0]["id"],))
        return rows[0]

    def ack_command(self, cmd_id, now=None):
        self.run("update commands set state='done', acked_ts=? where id=?", (now or time.time(), cmd_id))
