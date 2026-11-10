"""Scores the models on runs they were not trained on:  python -m detection.evaluate

The split is by experiment run, so neighbouring windows of one run never end up on both sides.
"""
import json
import sqlite3
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import GroupShuffleSplit

from gateway import settings
from . import dataset, rules


def latency(db_path):
    """Seconds from the start of each non-normal run to the first alert, per scenario."""
    con = sqlite3.connect(str(db_path))
    exps = pd.read_sql_query("select id, scenario, started from experiments "
                             "where ended is not null and scenario != 'normal'", con)
    ev = pd.read_sql_query("select experiment_id, ts, label from events where label != 'normal'", con)
    con.close()
    out = {}
    for e in exps.itertuples():
        hits = ev[(ev.experiment_id == e.id) & (ev.ts >= e.started)]
        if len(hits):
            out.setdefault(e.scenario, []).append(float(hits.ts.min() - e.started))
    return {k: {"mean_s": float(np.mean(v)), "runs": len(v)} for k, v in out.items()}


def main():
    cfg = settings.load()
    db = settings.resolve(cfg["gateway"]["db_path"])
    base = rules.load_baseline(settings.resolve(cfg["gateway"]["baseline_path"]))
    X, y, groups = dataset.build(db, cfg, base.get("base_current_a"))
    if len(set(groups)) < 4:
        raise SystemExit("Need at least four finished runs (repeat each scenario) before an evaluation makes sense.")

    train, test = next(GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=7).split(X, y, groups))
    rf = RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=7).fit(X[train], y[train])
    pred = rf.predict(X[test])
    labels = sorted(set(y))
    p, r, f1, _ = precision_recall_fscore_support(y[test], pred, labels=labels, average="macro", zero_division=0)
    normal = y[test] == "normal"
    report = {
        "windows": {"train": int(len(train)), "test": int(len(test))},
        "accuracy": float(accuracy_score(y[test], pred)),
        "precision_macro": float(p), "recall_macro": float(r), "f1_macro": float(f1),
        "false_positive_rate": float((pred[normal] != "normal").mean()) if normal.any() else None,
        "labels": labels,
        "confusion_matrix": confusion_matrix(y[test], pred, labels=labels).tolist(),
        "detection_latency": latency(db),
    }
    folder = settings.ROOT / "data" / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"eval_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print("saved to", path)


if __name__ == "__main__":
    main()
