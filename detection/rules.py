"""Statistical and timing checks. Each check raises a flag; the decision layer reads the flags."""
import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Flag:
    code: str
    node: str = ""
    detail: str = ""


def load_baseline(path):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


def _z(value, stats, floor):
    mean, std = stats
    return abs(value - mean) / max(std, floor)


def check(f, base, cfg, settling=False, branch_meter=True):
    r, period = cfg["rules"], cfg["gateway"]["sample_period_s"]
    flags = []
    state = "on" if f["relay_on"] == 1.0 else "off"
    stepped = []
    for key, node in (("a", "A"), ("b", "B")):
        n = f[f"{key}_n"]
        if n == 0:
            continue
        if f[f"{key}_seq_repeat"] > 0:
            flags.append(Flag("SEQ_REPEAT", node, "sequence numbers repeat or go backwards"))
        if f[f"{key}_seq_gap"] > 0:
            flags.append(Flag("SEQ_GAP", node, "messages are missing"))
        meter = branch_meter or key == "a"          # without a branch meter Node B only reports relay state
        if meter and f[f"{key}_stale_run"] >= r["stale_run"]:
            flags.append(Flag("STALE", node, "readings are frozen"))
        dt = f[f"{key}_dt_mean"]
        if not math.isnan(dt) and dt > r["late_factor"] * period:
            flags.append(Flag("LATE", node, f"messages arrive every {dt:.1f} s"))
        if not meter or n < cfg["gateway"]["min_samples"]:
            continue

        v, i = f[f"{key}_v_mean"], f[f"{key}_i_mean"]
        if not (r["v_min"] <= v <= r["v_max"]) or abs(i) > r["i_max_a"]:
            flags.append(Flag("RANGE", node, f"{v:.2f} V, {i:.3f} A is outside the expected range"))
        if not settling and (f[f"{key}_max_step_i"] > r["max_step_a"] or f[f"{key}_max_step_v"] > r["max_step_v"]):
            flags.append(Flag("STEP", node, "sudden jump between two samples"))
            stepped.append(node)
        stats = base.get("nodes", {}).get(node, {}).get(state)
        if stats and not settling:
            zi = _z(i, stats["i"], r["std_floor_a"])
            zv = _z(v, stats["v"], r["std_floor_v"])
            if max(zi, zv) > r["z_limit"]:
                flags.append(Flag("ZSCORE", node, f"{max(zi, zv):.1f} sigma from the baseline"))

    # a real load change moves both meters; a jump in only one of them is suspicious
    if branch_meter and len(stepped) == 1 and min(f["a_n"], f["b_n"]) >= cfg["gateway"]["min_samples"]:
        flags.append(Flag("LONE_STEP", stepped[0], "only this meter jumped"))
    if not math.isnan(f["resid"]) and abs(f["resid"]) > r["resid_tol_a"]:
        flags.append(Flag("RESID", "A", f"feeder current is off by {f['resid']:+.3f} A"))
    if not math.isnan(f["vgap"]) and f["vgap"] > r["vgap_tol_v"]:
        flags.append(Flag("VGAP", "A", f"INA226 and voltage sensor differ by {f['vgap']:.2f} V"))
    return flags
