"""Trains both models from the stored experiments:  python -m detection.train"""
from collections import Counter

from gateway import settings
from . import dataset, models, rules


def main():
    cfg = settings.load()
    base = rules.load_baseline(settings.resolve(cfg["gateway"]["baseline_path"]))
    X, y, _ = dataset.build(settings.resolve(cfg["gateway"]["db_path"]), cfg, base.get("base_current_a"))
    if len(X) == 0:
        raise SystemExit("No finished experiments yet. Run the scenarios from the dashboard first.")
    print("windows per label:", dict(Counter(map(str, y))))
    if "normal" not in y:
        raise SystemExit("At least one finished 'normal' run is needed.")
    if len(set(y)) < 2:
        print("Only the normal class so far. Record the other scenarios before trusting the Random Forest.")
    models.fit(X, y, settings.resolve(cfg["gateway"]["models_dir"]))
    print("models saved, restart the gateway to load them")


if __name__ == "__main__":
    main()
