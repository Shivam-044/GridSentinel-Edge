from detection.decision import Decider, classify
from detection.rules import Flag


def flags(*codes):
    return [Flag(c) for c in codes]


def test_labels():
    assert classify([]) == "normal"
    assert classify(flags("TIMEOUT")) == "comm_interruption"
    assert classify(flags("SEQ_REPEAT")) == "replay_stale"
    assert classify(flags("STEP", "ZSCORE")) == "physical_fault"
    assert classify(flags("STEP", "RESID")) == "cyber_anomaly"
    assert classify(flags("RESID")) == "sensor_anomaly"
    assert classify(flags("STEP", "LONE_STEP")) == "cyber_anomaly"
    assert classify(flags("RESID", "VGAP")) == "cyber_anomaly"


def test_alert_needs_quiet_windows_to_clear():
    d = Decider(clear_windows=3)
    assert d.update("physical_fault", 1.0)
    assert not d.update("normal", 2.0)
    assert not d.update("normal", 3.0)
    assert d.update("normal", 4.0)
    assert d.label == "normal"


def test_data_alert_keeps_its_first_label():
    d = Decider()
    assert d.update("cyber_anomaly", 1.0)
    assert not d.update("sensor_anomaly", 2.0)
    assert d.label == "cyber_anomaly"
