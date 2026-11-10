"""Gateway core: takes telemetry in, keeps short windows, runs detection once a second."""
import json
import threading
import time
from collections import deque

from detection import decision, features, models, rules
from scenarios.injector import Injector
from . import settings

NODES = ("A", "B")
DIGITAL = {"fdi", "drift", "replay", "interruption"}
COMMANDS = {"relay_on", "relay_off", "buzzer_on", "buzzer_off"}


class Engine:
    def __init__(self, cfg, store, baseline=None, ml=None):
        self.cfg, self.store = cfg, store
        g = cfg["gateway"]
        self.baseline = rules.load_baseline(settings.resolve(g["baseline_path"])) if baseline is None else baseline
        self.models = models.Models(settings.resolve(g["models_dir"])) if ml is None else ml
        self.branch_meter = cfg.get("sensing", {}).get("branch_meter", True)
        self.decider = decision.Decider(cfg["decision"]["clear_windows"])
        self.injector = Injector()
        self.rows = {n: deque() for n in NODES}
        self.last, self.seen = {}, {}
        self.started = None                    # time of the first message from any node
        self.experiment = None
        self.relay_changed = 0.0
        self.flags, self.ml_out = [], {}
        self.lock = threading.RLock()

    # ---- input -------------------------------------------------------------------------
    def ingest(self, msg, now=None):
        now = time.time() if now is None else now
        with self.lock:
            received = dict(msg)                       # the message exactly as the node sent it
            msg = self.injector.apply(dict(msg, injected=False), now)
            if msg is None or msg["node_id"] not in NODES:
                return False
            node = msg["node_id"]
            if self.started is None:
                self.started = now
            row = {k: msg.get(k) for k in ("seq", "uptime_ms", "bus_v", "current_a", "power_w",
                                           "vsense_v", "relay_on", "rssi", "fw")}
            row.update(ts=now, seq_flag=None, same=False)

            prev = self.last.get(node)
            if prev:
                step = row["seq"] - prev["seq"]
                rebooted = row["seq"] <= 2 and row["uptime_ms"] < prev["uptime_ms"]
                if not rebooted:
                    if step <= 0:
                        row["seq_flag"] = "repeat"
                    elif step > 1:
                        row["seq_flag"] = "gap"
                row["same"] = all(row[k] == prev[k] for k in ("bus_v", "current_a", "power_w"))
                if node == "B" and row["relay_on"] is not None and row["relay_on"] != prev["relay_on"]:
                    self.relay_changed = now

            self.rows[node].append(row)
            self.last[node], self.seen[node] = row, now
            exp = self.experiment
            injected = msg.get("injected", False)
            self.store.add_telemetry(dict(row, node_id=node, injected=injected,
                                          raw=json.dumps(received) if injected else None,
                                          scenario=exp["scenario"] if exp else None,
                                          experiment_id=exp["id"] if exp else None))
            return True

    # ---- detection ---------------------------------------------------------------------
    def _recent(self, node, now):
        horizon = now - self.cfg["gateway"]["window_s"]
        q = self.rows[node]
        while q and q[0]["ts"] < horizon:
            q.popleft()
        return list(q)

    def tick(self, now=None):
        """Called about once a second. Silence from a node is only visible from here."""
        now = time.time() if now is None else now
        with self.lock:
            flags = []
            for n in NODES:
                t = self.seen.get(n, self.started)     # a node that never reported is counted from the first message
                if t is not None and now - t > self.cfg["gateway"]["node_timeout_s"]:
                    flags.append(rules.Flag("TIMEOUT", n, f"no data for {now - t:.0f} s"))
            ra, rb = self._recent("A", now), self._recent("B", now)
            if not ra and not rb and not flags:
                return
            f = features.window(ra, rb, self.baseline.get("base_current_a"),
                                self.baseline.get("lamp2_current_a"), single_meter=not self.branch_meter)
            settling = now - self.relay_changed < self.cfg["rules"]["relay_settle_s"]
            flags += rules.check(f, self.baseline, self.cfg, settling, self.branch_meter)
            label, source = decision.classify(flags), "rules"

            ml = self.models.score(f)
            if label == "normal" and ml.get("label") not in (None, "normal") \
                    and ml.get("proba", 0) >= self.cfg["decision"]["model_min_proba"]:
                label, source = ml["label"], "model"

            self.flags, self.ml_out = flags, ml
            before = self.decider.label
            if self.decider.update(label, now):
                self._on_change(now, before, source, flags, ml)

    def _on_change(self, now, before, source, flags, ml):
        label, resp = self.decider.label, []
        rc = self.cfg["response"]
        if label != "normal":
            if rc["buzzer_on_alert"]:
                self.store.queue_command("B", "buzzer_on", decision.OLED_TEXT.get(label, "Alert"), now)
                resp.append("buzzer")
            if rc["auto_relay_off"] and self.experiment and label in rc["auto_relay_labels"]:
                self.store.queue_command("B", "relay_off", "", now)
                resp.append("lamp 2 off")
        elif before != "normal" and rc["buzzer_on_alert"]:
            self.store.queue_command("B", "buzzer_off", "", now)
        exp = self.experiment
        self.store.add_event(now, label, source,
                             {"flags": [vars(f) for f in flags], "model": ml},
                             ", ".join(resp), exp["id"] if exp else None, exp["scenario"] if exp else None)

    # ---- experiments -------------------------------------------------------------------
    def start_experiment(self, name, scenario, node="A", field="current_a", params=None, now=None):
        now = time.time() if now is None else now
        if scenario not in decision.SCENARIO_LABEL:
            raise ValueError(f"unknown scenario {scenario}")
        with self.lock:
            self.stop_experiment(now)
            if scenario in DIGITAL:
                self.injector.start(scenario, node, field, now, **(params or {}))
            exp_id = self.store.start_experiment(name, scenario, node, field, params or {}, now)
            self.experiment = {"id": exp_id, "name": name, "scenario": scenario, "started": now}
            return exp_id

    def stop_experiment(self, now=None):
        with self.lock:
            self.injector.clear()
            if self.experiment:
                self.store.end_experiment(self.experiment["id"], now)
            self.experiment = None

    # ---- read side ---------------------------------------------------------------------
    def status(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            nodes = {}
            for n in NODES:
                r = self.last.get(n)
                nodes[n] = {"seen": r is not None,
                            "age_s": round(now - self.seen[n], 1) if n in self.seen else None,
                            **({k: r[k] for k in ("seq", "bus_v", "current_a", "power_w", "vsense_v",
                                                  "relay_on", "rssi", "fw")} if r else {})}
            return {
                "time": now,
                "nodes": nodes,
                "decision": {"label": self.decider.label, "since": self.decider.since,
                             "flags": [vars(f) for f in self.flags]},
                "experiment": self.experiment,
                "injection": {"mode": self.injector.mode, "node": self.injector.node, "field": self.injector.field},
                "branch_meter": self.branch_meter,
                "baseline_loaded": bool(self.baseline.get("base_current_a") is not None),
                "models": self.models.loaded,
                "simulated": any((r.get("fw") or "") == "simulator" for r in self.last.values()),
            }
