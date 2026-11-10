"""Isolation Forest (trained on normal windows) and Random Forest (trained on labelled runs)."""
from pathlib import Path

from . import features

ISO, RF = "isolation_forest.joblib", "random_forest.joblib"


def _load(path):
    if not path.exists():
        return None
    import joblib   # only needed once models exist
    return joblib.load(path)


class Models:
    def __init__(self, folder):
        folder = Path(folder)
        self.iso = _load(folder / ISO)
        self.rf = _load(folder / RF)

    @property
    def loaded(self):
        return {"isolation_forest": self.iso is not None, "random_forest": self.rf is not None}

    def score(self, f):
        out = {}
        if self.iso is None and self.rf is None:
            return out
        x = features.vector(f).reshape(1, -1)
        if self.iso is not None:
            out["iso_anomaly"] = bool(self.iso.predict(x)[0] == -1)
            out["iso_score"] = float(self.iso.score_samples(x)[0])
        if self.rf is not None:
            p = self.rf.predict_proba(x)[0]
            k = int(p.argmax())
            out["label"], out["proba"] = str(self.rf.classes_[k]), float(p[k])
        return out


def fit(X, y, folder, seed=7):
    """X is a 2-D array of feature vectors, y the matching labels."""
    import joblib
    from sklearn.ensemble import IsolationForest, RandomForestClassifier
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    normal = X[[label == "normal" for label in y]]
    if len(normal) >= 20:
        iso = IsolationForest(n_estimators=200, contamination="auto", random_state=seed).fit(normal)
        joblib.dump(iso, folder / ISO)
    rf = RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=seed).fit(X, y)
    joblib.dump(rf, folder / RF)
    return rf
