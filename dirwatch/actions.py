"""Executing a triage decision against a file and recording it in the db."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from send2trash import send2trash

from .db import Database
from .models import Item, Status


class ActionError(Exception):
    pass


def keep(db: Database, item: Item) -> None:
    """Leave the file where it is; never prompt for it again."""
    db.set_status(item.id, Status.KEPT)


def ignore(db: Database, item: Item) -> None:
    """Like keep, but semantically 'stop bothering me about this'."""
    db.set_status(item.id, Status.IGNORED)


def delete(db: Database, item: Item) -> None:
    """Move the file to the system Trash (recoverable)."""
    if item.exists():
        try:
            send2trash(item.path)
        except Exception as exc:  # send2trash raises plain OSError subclasses
            raise ActionError(f"Could not trash {item.name}: {exc}") from exc
    db.set_status(item.id, Status.DELETED)


def move(db: Database, item: Item, dest_dir: str | Path) -> Path:
    """Move the file into dest_dir, avoiding clobbering an existing name."""
    dest_dir = Path(dest_dir).expanduser()
    if not item.exists():
        raise ActionError(f"{item.name} no longer exists")
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = _unique_target(dest_dir / item.name)
        shutil.move(item.path, target)
    except OSError as exc:
        raise ActionError(f"Could not move {item.name}: {exc}") from exc
    db.set_status(item.id, Status.MOVED, new_path=str(target))
    return target


def snooze(db: Database, item: Item, seconds: float) -> float:
    """Resurface this item after `seconds`."""
    until = time.time() + seconds
    db.set_status(item.id, Status.SNOOZED, snooze_until=until)
    return until


def _unique_target(target: Path) -> Path:
    if not target.exists():
        return target
    stem, suffix, parent = target.stem, target.suffix, target.parent
    i = 1
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


# Snooze presets shown in the popup, label -> seconds.
SNOOZE_PRESETS: list[tuple[str, int]] = [
    ("1 hour", 3600),
    ("This evening", 6 * 3600),
    ("Tomorrow", 24 * 3600),
    ("Next week", 7 * 24 * 3600),
]
