"""Load config.yaml + .env into one place."""
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
STATE = ROOT / "state"


def load_config():
    with open(ROOT / "config.yaml", "r") as f:
        cfg = yaml.safe_load(f)

    # Pull a local .env into the environment if present (no extra dependency).
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

    WORK.mkdir(exist_ok=True)
    STATE.mkdir(exist_ok=True)
    return cfg


def env(name, default=""):
    return os.environ.get(name, default) or default
