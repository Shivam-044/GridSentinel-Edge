"""End to end through the gateway core, with a clock we control."""
from types import SimpleNamespace

from gateway import settings
from gateway.db import Store
from gateway.engine import Engine

CFG = settings.load()
LAMP = 0.417


def make():
    ml = SimpleNamespace(score=lambda f: {}, loaded={})
    eng = Engine(CFG, Store(":memory:"), baseline={"base_current_a": LAMP, "nodes": {}}, ml=ml)
    return eng, {"t": 1000.0, "seq": 0, "relay": False, "lamp2": True}


def run(eng, st, seconds):
    """Two messages per second from each node, one tick per second."""
    for _ in range(int(seconds * 2)):
        st["t"] += 0.5
        st["seq"] += 1
        ib = LAMP if (st["relay"] and st["lamp2"]) else 0.0
        common = {"seq": st["seq"], "uptime_ms": int(st["seq"] * 500), "bus_v": 12.0 + 0.002 * (st["seq"] % 5)}
        eng.ingest({"node_id": "A", "current_a": min(ib + LAMP + 0.001 * (st["seq"] % 4), 0.8192), "power_w": 5.0,   # the INA226 clips at 0.8192 A
                    "vsense_v": 12.0, **common}, st["t"])
        eng.ingest({"node_id": "B", "current_a": ib + 0.001 * (st["seq"] % 3), "power_w": 4.0,
                    "relay_on": st["relay"], **common}, st["t"])
        if st["seq"] % 2 == 0:
            eng.tick(st["t"])


def label(eng):
    return eng.status()["decision"]["label"]


def test_normal_run_stays_quiet():
    eng, st = make()
    run(eng, st, 30)
    assert label(eng) == "normal"


def test_relay_switching_is_not_an_alert():
    eng, st = make()
    run(eng, st, 15)
    st["relay"] = True
    run(eng, st, 20)
    assert label(eng) == "normal"


def test_false_data_injection():
    eng, st = make()
    run(eng, st, 20)
    eng.start_experiment("t", "fdi", "A", "current_a", {"factor": 0.6}, st["t"])
    run(eng, st, 12)
    assert label(eng) == "cyber_anomaly"
    first = eng.store.query("select label from events order by id")[0]["label"]
    assert first == "cyber_anomaly"      # no physical-fault flicker before the data alert


def test_sensor_drift():
    eng, st = make()
    run(eng, st, 20)
    eng.start_experiment("t", "drift", "A", "current_a", {"rate_per_min": 0.6}, st["t"])
    run(eng, st, 30)
    assert label(eng) == "sensor_anomaly"


def test_replay():
    eng, st = make()
    run(eng, st, 25)
    eng.start_experiment("t", "replay", "A", "current_a", {"depth": 10}, st["t"])
    run(eng, st, 8)
    assert label(eng) == "replay_stale"


def test_interruption():
    eng, st = make()
    run(eng, st, 20)
    eng.start_experiment("t", "interruption", "B", "current_a", {}, st["t"])
    run(eng, st, 8)
    assert label(eng) == "comm_interruption"


def test_lamp_removed_is_a_physical_fault():
    eng, st = make()
    st["relay"] = True
    run(eng, st, 25)
    st["lamp2"] = False
    run(eng, st, 10)
    assert label(eng) == "physical_fault"


def test_alert_queues_a_buzzer_command():
    eng, st = make()
    run(eng, st, 20)
    eng.start_experiment("t", "fdi", "A", "current_a", {"factor": 0.6}, st["t"])
    run(eng, st, 12)
    cmd = eng.store.next_command("B")
    assert cmd["command"] == "buzzer_on"


def test_original_message_is_kept_next_to_the_injected_one():
    eng, st = make()
    run(eng, st, 10)
    eng.start_experiment("t", "fdi", "A", "current_a", {"factor": 0.5}, st["t"])
    run(eng, st, 3)
    row = eng.store.query("select current_a, raw from telemetry where injected = 1 and node_id = 'A' limit 1")[0]
    import json
    assert json.loads(row["raw"])["current_a"] > row["current_a"] * 1.5
    clean = eng.store.query("select raw from telemetry where injected = 0 limit 1")[0]
    assert clean["raw"] is None


def test_node_that_never_reports_is_counted_as_lost():
    eng, st = make()
    for _ in range(14):                       # only Node A ever speaks
        st["t"] += 0.5
        st["seq"] += 1
        eng.ingest({"node_id": "A", "seq": st["seq"], "uptime_ms": st["seq"] * 500, "bus_v": 12.0,
                    "current_a": 0.4 + 0.001 * (st["seq"] % 3), "power_w": 4.8, "vsense_v": 12.0}, st["t"])
        if st["seq"] % 2 == 0:
            eng.tick(st["t"])
    assert label(eng) == "comm_interruption"
