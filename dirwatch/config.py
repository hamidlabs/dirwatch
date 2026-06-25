"""User configuration: watched directories and behavior settings.

Stored as JSON so the settings window can read and write it without a TOML
serializer. The file lives at ~/.config/dirwatch/config.json.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .paths import config_file


@dataclass
class WatchedDir:
    path: str
    enabled: bool = True

    def resolved(self) -> Path:
        return Path(self.path).expanduser()


@dataclass
class Config:
    # Directories we watch for new files.
    watched: list[WatchedDir] = field(default_factory=list)
    # Seconds a file's size must stay unchanged before we consider it "settled".
    debounce_seconds: int = 4
    # When a directory is first added, treat files already in it as known
    # (do not prompt). Set True to triage the existing backlog too.
    prompt_existing_on_add: bool = False
    # Ignore dotfiles and these temp/partial-download extensions.
    ignore_extensions: list[str] = field(
        default_factory=lambda: [
            ".crdownload", ".part", ".partial", ".download",
            ".tmp", ".temp", ".opdownload",
        ]
    )
    ignore_hidden: bool = True
    # Don't prompt while a file is open in another app (e.g. a video you're
    # watching); wait until it's closed.
    skip_in_use: bool = True
    # Start watching automatically when the app launches.
    autostart_watching: bool = True
    # Launch dirwatch on login (managed via an XDG autostart entry).
    autostart_login: bool = False
    # When this many files are waiting, show the batch Review window instead of
    # one card at a time.
    batch_threshold: int = 5
    # Resolved rows (deleted/moved/missing) older than this are pruned.
    retention_days: int = 30
    # Whether we have already applied the compositor floating rule.
    floating_configured: bool = False

    @staticmethod
    def default() -> "Config":
        downloads = Path.home() / "Downloads"
        return Config(watched=[WatchedDir(path=str(downloads), enabled=True)])

    @classmethod
    def load(cls) -> "Config":
        path = config_file()
        if not path.exists():
            cfg = cls.default()
            cfg.save()
            return cfg
        try:
            raw = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return cls.default()
        watched = [WatchedDir(**w) for w in raw.get("watched", [])]
        known = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in raw.items() if k in known and k != "watched"}
        return cls(watched=watched, **kwargs)

    def save(self) -> None:
        data = asdict(self)
        config_file().write_text(json.dumps(data, indent=2))

    def enabled_dirs(self) -> list[Path]:
        return [w.resolved() for w in self.watched if w.enabled]
