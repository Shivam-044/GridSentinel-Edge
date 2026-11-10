from detection import features, rules
from gateway import settings

CFG = settings.load()
BASE = {"base_current_a": 0.417, "nodes": {}}


def rows(n, current, relay=None, start=0.0, vs=12.0, **extra):
    out = []
    for k in range(n):
        out.append({"ts": start + k * 0.5, "bus_v": 12.0 + 0.001 * (k % 3), "current_a": current + 0.001 * (k % 4),
                    "power_w": 12.0 * current, "vsense_v": vs, "relay_on": relay, "seq_flag": None, "same": False, **extra})
    return out


def codes(ra, rb, base=BASE["base_current_a"]):
    f = features.window(ra, rb, base)
    return {x.code for x in rules.check(f, BASE, CFG)}


def test_quiet_window_raises_nothing():
    assert codes(rows(20, 0.80), rows(20, 0.417, relay=True)) == set()


def test_feeder_that_disagrees_with_branch_is_flagged():
    assert "RESID" in codes(rows(20, 0.55), rows(20, 0.417, relay=True))


def test_voltage_channels_that_disagree_are_flagged():
    assert "VGAP" in codes(rows(20, 0.417, vs=11.0), rows(20, 0.0, relay=False))


def test_frozen_readings_are_stale():
    frozen = rows(20, 0.417)
    for r in frozen:
        r.update(same=True)
    assert "STALE" in codes(frozen, rows(20, 0.0, relay=False))


def test_repeated_sequence_numbers():
    rep = rows(20, 0.417)
    rep[10]["seq_flag"] = "repeat"
    assert "SEQ_REPEAT" in codes(rep, rows(20, 0.0, relay=False))


def test_settling_hides_the_step_after_a_relay_command():
    ra = rows(10, 0.417) + rows(10, 0.834, start=5.0)
    f = features.window(ra, rows(20, 0.417, relay=True), 0.417)
    assert "STEP" in {x.code for x in rules.check(f, BASE, CFG)}
    assert "STEP" not in {x.code for x in rules.check(f, BASE, CFG, settling=True)}
