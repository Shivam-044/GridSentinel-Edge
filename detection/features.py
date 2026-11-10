"""Window features. The rules, the models and the training code all read from here."""
import bisect

import numpy as np

NAN = float("nan")
PER_NODE = ["n", "v_mean", "v_std", "i_mean", "i_std", "p_mean", "di", "max_step_i", "max_step_v",
            "dt_mean", "dt_std", "seq_repeat", "seq_gap", "stale_run"]
CROSS = ["resid", "vgap", "vab", "relay_on"]
FEATURE_NAMES = [f"{n}_{k}" for n in ("a", "b") for k in PER_NODE] + CROSS


def _node(rows):
    out = dict.fromkeys(PER_NODE, NAN)
    out.update(n=len(rows), seq_repeat=0.0, seq_gap=0.0, stale_run=0.0)
    if not rows:
        return out
    v = np.array([r["bus_v"] for r in rows])
    i = np.array([r["current_a"] for r in rows])
    p = np.array([r["power_w"] for r in rows])
    t = np.array([r["ts"] for r in rows])
    out.update(v_mean=v.mean(), v_std=v.std(), i_mean=i.mean(), i_std=i.std(), p_mean=p.mean(), di=i[-1] - i[0])
    out["max_step_i"] = np.abs(np.diff(i)).max() if len(i) > 1 else 0.0
    out["max_step_v"] = np.abs(np.diff(v)).max() if len(v) > 1 else 0.0
    if len(t) > 1:
        dt = np.diff(t)
        out["dt_mean"], out["dt_std"] = dt.mean(), dt.std()
    out["seq_repeat"] = float(sum(r.get("seq_flag") == "repeat" for r in rows))
    out["seq_gap"] = float(sum(r.get("seq_flag") == "gap" for r in rows))
    run = 0
    for r in reversed(rows):
        if not r.get("same"):
            break
        run += 1
    out["stale_run"] = float(run)
    return out


def _expected_resid(rows_a, rows_b, base, lamp2):
    """One-meter mode: feeder current minus what the relay state says it should be."""
    if base is None or lamp2 is None or not rows_a:
        return NAN
    ts_b = [r["ts"] for r in rows_b]
    diffs = []
    for r in rows_a:
        k = bisect.bisect_right(ts_b, r["ts"]) - 1
        relay = bool(rows_b[k].get("relay_on")) if k >= 0 else False
        diffs.append(r["current_a"] - base - (lamp2 if relay else 0.0))
    return float(np.mean(diffs))


def window(rows_a, rows_b, base_current=None, lamp2_current=None, single_meter=False):
    """Features for one analysis window. Rows are the dicts the gateway keeps per node.

    With single_meter the branch has no INA226, so the residual compares the feeder current with
    lamp 1 plus lamp 2 whenever the relay is on."""
    f = {}
    for name, rows in (("a", rows_a), ("b", rows_b)):
        f.update({f"{name}_{k}": v for k, v in _node(rows).items()})
    both = bool(rows_a) and bool(rows_b)
    vs = [r["vsense_v"] for r in rows_a if r.get("vsense_v") is not None]
    f["vgap"] = abs(f["a_v_mean"] - float(np.mean(vs))) if vs else NAN
    f["vab"] = f["a_v_mean"] - f["b_v_mean"] if (both and not single_meter) else NAN
    if single_meter:
        f["resid"] = _expected_resid(rows_a, rows_b, base_current, lamp2_current)
    else:
        f["resid"] = f["a_i_mean"] - f["b_i_mean"] - base_current if (both and base_current is not None) else NAN
    relay = rows_b[-1].get("relay_on") if rows_b else None
    f["relay_on"] = float(bool(relay)) if relay is not None else NAN
    return f


def vector(f):
    """Fixed-order numeric vector for the models. Missing values become zero."""
    return np.array([0.0 if np.isnan(f[k]) else f[k] for k in FEATURE_NAMES], dtype=float)
