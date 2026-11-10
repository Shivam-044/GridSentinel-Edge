from scenarios.injector import Injector


def msg(node="A", seq=1, i=0.8):
    return {"node_id": node, "seq": seq, "uptime_ms": seq * 500, "bus_v": 12.0, "current_a": i, "power_w": 12.0 * i}


def test_nothing_changes_when_idle():
    inj = Injector()
    assert inj.apply(msg(), 0) == msg()


def test_fdi_scales_one_field_and_keeps_power_consistent():
    inj = Injector()
    inj.start("fdi", "A", "current_a", now=0, factor=0.5)
    out = inj.apply(msg(i=0.8), 1)
    assert abs(out["current_a"] - 0.4) < 1e-9 and abs(out["power_w"] - 4.8) < 1e-9 and out["injected"]
    assert inj.apply(msg("B", i=0.4), 1)["current_a"] == 0.4


def test_drift_grows_with_time():
    inj = Injector()
    inj.start("drift", "A", "current_a", now=0, rate_per_min=0.6)
    assert abs(inj.apply(msg(i=0.8), 10)["current_a"] - 0.9) < 1e-9
    assert abs(inj.apply(msg(i=0.8), 20)["current_a"] - 1.0) < 1e-9


def test_replay_sends_old_sequence_numbers():
    inj = Injector()
    for s in range(1, 31):
        inj.apply(msg(seq=s), s)
    inj.start("replay", "A", now=31, depth=5)
    seqs = [inj.apply(msg(seq=40 + k), 32 + k)["seq"] for k in range(6)]
    assert seqs == [26, 27, 28, 29, 30, 26]


def test_interruption_drops_the_chosen_node_only():
    inj = Injector()
    inj.start("interruption", "B")
    assert inj.apply(msg("B"), 1) is None
    assert inj.apply(msg("A"), 1) is not None
