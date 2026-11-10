import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path=None):
    with open(path or ROOT / "config.toml", "rb") as fh:
        return tomllib.load(fh)


def resolve(relative):
    """Paths in config.toml are relative to the project root."""
    p = Path(relative)
    return p if p.is_absolute() else ROOT / p
