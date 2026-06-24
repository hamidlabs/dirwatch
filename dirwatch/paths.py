"""Standard XDG paths for config and data."""
from __future__ import annotations

import os
from pathlib import Path

from . import APP_NAME


def _xdg(env: str, default: str) -> Path:
    base = os.environ.get(env)
    root = Path(base) if base else Path.home() / default
    return root / APP_NAME


def config_dir() -> Path:
    d = _xdg("XDG_CONFIG_HOME", ".config")
    d.mkdir(parents=True, exist_ok=True)
    return d


def data_dir() -> Path:
    d = _xdg("XDG_DATA_HOME", ".local/share")
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_file() -> Path:
    return config_dir() / "config.json"


def db_file() -> Path:
    return data_dir() / "dirwatch.db"
