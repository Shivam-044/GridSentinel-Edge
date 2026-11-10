"""Test module that disturbs telemetry on its way into the gateway. The circuit is never touched."""
from collections import deque

FIELDS = ("bus_v", "current_a", "vsense_v")


class Injector:
    def __init__(self):
        self.history = {}
        self.clear()

    def clear(self):
        self.mode = None
        self.node = "A"
        self.field = "current_a"
        self.params = {}
        self.t0 = 0.0
        self._tape = []
        self._pos = 0

    def start(self, mode, node="A", field="current_a", now=0.0, **params):
        if mode not in ("fdi", "drift", "replay", "interruption"):
            raise ValueError(f"unknown scenario {mode}")
        if field not in FIELDS:
            raise ValueError(f"cannot inject into {field}")
        self.clear()
        self.mode, self.node, self.field, self.params, self.t0 = mode, node, field, params, now
        if mode == "replay":
            old = list(self.history.get(node, []))
            self._tape = old[-int(params.get("depth", 20)):]

    def apply(self, msg, now):
        """Returns the message to use, or None when the test module drops it."""
        node = msg["node_id"]
        hist = self.history.setdefault(node, deque(maxlen=200))
        if self.mode is None or node != self.node:
            hist.append(dict(msg))
            return msg
        if self.mode == "interruption":
            return None
        if self.mode == "replay":
            if not self._tape:
                return msg
            old = dict(self._tape[self._pos % len(self._tape)])
            self._pos += 1
            old["injected"] = True
            return old
        out = dict(msg)
        value = out.get(self.field)
        if value is None:
            return out
        if self.mode == "fdi":
            value = value * self.params.get("factor", 1.0) + self.params.get("offset", 0.0)
        else:
            value = value + self.params.get("rate_per_min", 0.1) * (now - self.t0) / 60.0
        out[self.field] = value
        if self.field in ("bus_v", "current_a"):
            out["power_w"] = out["bus_v"] * out["current_a"]   # keep the message internally consistent
        out["injected"] = True
        return out
