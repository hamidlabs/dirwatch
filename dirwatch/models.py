"""Core data types shared across the watcher, engine, db and UI."""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Status(str, Enum):
    PENDING = "pending"      # waiting for the user to triage
    SNOOZED = "snoozed"      # will resurface at snooze_until
    KEPT = "kept"            # user chose to keep
    DELETED = "deleted"      # sent to trash
    MOVED = "moved"          # moved elsewhere
    IGNORED = "ignored"      # never prompt for this file again
    BASELINE = "baseline"    # already present when the dir was first watched
    MISSING = "missing"      # vanished before the user acted


# Statuses that mean "do not prompt for this path again".
RESOLVED = {
    Status.KEPT, Status.DELETED, Status.MOVED,
    Status.IGNORED, Status.BASELINE, Status.MISSING,
}


@dataclass
class Item:
    """A file under consideration, mirrored in the database."""
    path: str
    inode: int
    size: int
    watch_dir: str
    status: Status = Status.PENDING
    first_seen: float = 0.0
    decided_at: float | None = None
    snooze_until: float | None = None
    is_dir: bool = False
    id: int | None = None

    @property
    def p(self) -> Path:
        return Path(self.path)

    @property
    def name(self) -> str:
        return self.p.name

    @property
    def age_seconds(self) -> float:
        return max(0.0, time.time() - self.first_seen)

    def exists(self) -> bool:
        return self.p.exists()
