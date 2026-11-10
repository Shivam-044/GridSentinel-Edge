"""One INA226 only, on the feeder. Node B reports relay state and zeros for the rest."""
import copy
from types import SimpleNamespace

from gateway import settings
from gateway.db import Store
from gateway.engine import Engine

LAMP = 0.40
CFG = copy.deepcopy(settings.load())
CFG["sensing"]["branch_meter"] = False


def make():
    ml = SimpleNamespace(score=lambda f: {}, loaded={})
    base = {"base_current_a": LAMP, "lamp2_current_a": LAMP, "nodes": {}}
    return Engine(CFG, Store(":memory:"), baseline=base, ml=ml), {"t": 1000.0, "seq": 0, "relay": False}


def run(eng, st, seconds):
    for _ in range(int(seconds * 2)):
        st["t"] += 0.5
        st["seq"] += 1
        common = {"seq": st["seq"], "uptime_ms": int(st["seq"] * 500)}
        feeder = LAMP + (LAMP if st["relay"] else 0.0) + 0.001 * (st["seq"] % 4)
        eng.ingest({"node_id": "A", "bus_v": 12.0 + 0.002 * (st["seq"] % 5), "current_a": feeder,
                    "power_w": 5.0, "vsense_v": 12.0, **common}, st["t"])
        eng.ingest({"node_id": "B", "bus_v": 0.0, "current_a": 0.0, "power_w": 0.0, "relay_on": st["relay"], **common}, st["t"])
        if st["seq"] % 2 == 0:
            eng.tick(st["t"])


def label(eng):
    return eng.status()["decision"]["label"]


def test_normal_run_with_relay_switching_stays_quiet():
    eng, st = make()
    run(eng, st, 20)
    st["relay"] = True
    run(eng, st, 25)
    st["relay"] = False
    run(eng, st, 25)
    assert label(eng) == "normal"


def test_false_data_on_the_feeder_current_is_caught():
    eng, st = make()
    run(eng, st, 20)
    eng.start_experiment("t", "fdi", "A", "current_a", {"factor": 0.5}, st["t"])
    run(eng, st, 12)
    assert label(eng) == "cyber_anomaly"


def test_voltage_manipulation_disagrees_with_the_voltage_sensor():
    eng, st = make()
    run(eng, st, 20)
    eng.start_experiment("t", "fdi", "A", "bus_v", {"offset": 1.5}, st["t"])
    run(eng, st, 12)
    assert label(eng) == "cyber_anomaly"


def test_replay_and_lost_link_still_work():
    eng, st = make()
    run(eng, st, 25)
    eng.start_experiment("t", "replay", "A", "current_a", {"depth": 10}, st["t"])
    run(eng, st, 8)
    assert label(eng) == "replay_stale"
    eng2, st2 = make()
    run(eng2, st2, 20)
    eng2.start_experiment("t", "interruption", "B", "current_a", {}, st2["t"])
    run(eng2, st2, 8)
    assert label(eng2) == "comm_interruption"
