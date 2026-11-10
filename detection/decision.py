"""Turns rule flags into one label, and keeps an alert steady while it lasts."""

SCENARIO_LABEL = {
    "normal": "normal",
    "physical_fault": "physical_fault",
    "fdi": "cyber_anomaly",
    "drift": "sensor_anomaly",
    "replay": "replay_stale",
    "interruption": "comm_interruption",
}

LABEL_TEXT = {
    "normal": "Normal",
    "physical_fault": "Physical fault",
    "sensor_anomaly": "Sensor anomaly",
    "cyber_anomaly": "Data anomaly",
    "replay_stale": "Replay or stale data",
    "comm_interruption": "Link lost",
}

OLED_TEXT = {
    "physical_fault": "Physical fault",
    "sensor_anomaly": "Sensor anomaly",
    "cyber_anomaly": "Data anomaly",
    "replay_stale": "Replay detected",
    "comm_interruption": "Link lost",
}

LATCHED = {"cyber_anomaly", "sensor_anomaly"}


def classify(flags):
    codes = {f.code for f in flags}
    if "TIMEOUT" in codes:
        return "comm_interruption"
    if codes & {"SEQ_REPEAT", "STALE"}:
        return "replay_stale"
    if codes & {"LATE", "SEQ_GAP"}:
        return "comm_interruption"
    if codes & {"RESID", "VGAP", "LONE_STEP"}:
        # an abrupt change that the second view does not confirm points at the data,
        # a slow slide points at a sensor
        if "STEP" in codes or {"RESID", "VGAP"} <= codes:
            return "cyber_anomaly"
        return "sensor_anomaly"
    if codes & {"RANGE", "STEP", "ZSCORE"}:
        return "physical_fault"
    return "normal"


class Decider:
    def __init__(self, clear_windows=3):
        self.clear_windows = clear_windows
        self.label = "normal"
        self.since = 0.0
        self._quiet = 0

    def update(self, label, now):
        """Returns True when the reported state changed."""
        if label == "normal":
            if self.label == "normal":
                return False
            self._quiet += 1
            if self._quiet < self.clear_windows:
                return False
            self.label, self.since, self._quiet = "normal", now, 0
            return True
        self._quiet = 0
        if self.label == label:
            return False
        # a data alert keeps the label it started with, even when the evidence shifts later
        if self.label in LATCHED and label in LATCHED:
            return False
        self.label, self.since = label, now
        return True
