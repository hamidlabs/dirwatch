"""The brain: turns raw filesystem activity into triage-ready items.

Pure Python, no Qt. The owner (app or a test) drives it by calling tick()
on a timer, and supplies an `on_item_ready` callback that is invoked, on the
calling thread, whenever a file is ready to be triaged.
"""
from __future__ import annotations

import os
import stat
import time
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .db import Database
from .models import RESOLVED, Item, Status

ItemReady = Callable[[Item], None]


@dataclass
class _Candidate:
    watch_dir: str
    last_sig: tuple | None = None
    stable_since: float = field(default_factory=time.time)

# Cap the directory walk so a huge tree can't stall a tick.
_MAX_WALK = 20000


class Engine:
    def __init__(
        self,
        config: Config,
        db: Database,
        on_item_ready: ItemReady,
        *,
        clock: Callable[[], float] = time.time,
    ):
        self._cfg = config
        self._db = db
        self._on_ready = on_item_ready
        self._now = clock
        self._candidates: dict[str, _Candidate] = {}
        self._lock = threading.Lock()

    # ---- intake (called from the watcher thread) ---------------------------

    def note_candidate(self, path: str, watch_dir: str) -> None:
        with self._lock:
            if path not in self._candidates:
                self._candidates[path] = _Candidate(
                    watch_dir=watch_dir, stable_since=self._now()
                )

    # ---- policy helpers ----------------------------------------------------

    def _is_ignored(self, path: str) -> bool:
        name = Path(path).name
        if self._cfg.ignore_hidden and name.startswith("."):
            return True
        suffix = Path(path).suffix.lower()
        return suffix in self._cfg.ignore_extensions

    # ---- baselining --------------------------------------------------------

    def baseline_dir(self, directory: Path) -> None:
        """Record files already present so they are not prompted later."""
        key = str(directory)
        if self._db.is_dir_baselined(key):
            return
        if not self._cfg.prompt_existing_on_add:
            now = self._now()
            try:
                entries = list(directory.iterdir())
            except OSError:
                entries = []
            for entry in entries:
                if self._is_ignored(str(entry)):
                    continue
                is_dir = entry.is_dir()
                if not (entry.is_file() or is_dir):
                    continue
                try:
                    st = entry.stat()
                except OSError:
                    continue
                self._db.upsert(
                    Item(
                        path=str(entry), inode=st.st_ino,
                        size=0 if is_dir else st.st_size,
                        watch_dir=key, status=Status.BASELINE, first_seen=now,
                        is_dir=is_dir,
                    )
                )
        self._db.mark_dir_baselined(key)

    # ---- main loop ---------------------------------------------------------

    def tick(self) -> None:
        """Promote settled candidates and wake due snoozes. Call ~1x/second."""
        for item in self._settled_items():
            self._deliver(item)
        for item in self._db.due_snoozed(self._now()):
            self._wake(item)

    def _probe(self, path: str) -> dict | None | str:
        """Return a stability snapshot, "skip" on a transient error, or None if
        the path is gone. For a directory the signature spans its whole tree, so
        an in-progress extraction keeps changing until it finishes."""
        try:
            st = os.stat(path)
        except (FileNotFoundError, NotADirectoryError):
            return None
        except OSError:
            return "skip"
        if not stat.S_ISDIR(st.st_mode):
            return {"sig": ("f", st.st_size), "is_dir": False,
                    "size": st.st_size, "inode": st.st_ino}
        count = total = 0
        newest = st.st_mtime
        for root, _dirs, files in os.walk(path):
            for name in files:
                try:
                    s = os.stat(os.path.join(root, name))
                except OSError:
                    continue
                count += 1
                total += s.st_size
                if s.st_mtime > newest:
                    newest = s.st_mtime
            if count > _MAX_WALK:
                break
        return {"sig": ("d", count, total, int(newest)), "is_dir": True,
                "size": total, "inode": st.st_ino}

    def _settled_items(self) -> list[Item]:
        now = self._now()
        ready: list[Item] = []
        with self._lock:
            paths = list(self._candidates)
        for path in paths:
            cand = self._candidates.get(path)
            if cand is None:
                continue
            if self._is_ignored(path):
                self._drop(path)
                continue
            probe = self._probe(path)
            if probe is None:
                self._drop(path)
                continue
            if probe == "skip":
                continue
            if cand.last_sig != probe["sig"]:
                cand.last_sig = probe["sig"]
                cand.stable_since = now
                continue
            if now - cand.stable_since < self._cfg.debounce_seconds:
                continue
            # Settled.
            self._drop(path)
            item = self._consider(
                path, probe["inode"], probe["size"], cand.watch_dir, now,
                probe["is_dir"],
            )
            if item is not None:
                ready.append(item)
        return ready

    def _consider(
        self, path: str, inode: int, size: int, watch_dir: str, now: float,
        is_dir: bool = False,
    ) -> Item | None:
        existing = self._db.get(path, inode)
        if existing is not None:
            if existing.status in RESOLVED:
                return None
            if existing.status in (Status.PENDING, Status.SNOOZED):
                return None  # already queued elsewhere
        item = Item(
            path=path, inode=inode, size=size, watch_dir=watch_dir,
            status=Status.PENDING, first_seen=now, is_dir=is_dir,
        )
        return self._db.upsert(item)

    def _wake(self, item: Item) -> None:
        if not item.exists():
            self._db.set_status(item.id, Status.MISSING)
            return
        self._db.set_status(item.id, Status.PENDING)
        item.status = Status.PENDING
        self._deliver(item)

    def _deliver(self, item: Item) -> None:
        if not item.exists():
            self._db.set_status(item.id, Status.MISSING)
            return
        self._on_ready(item)

    def _drop(self, path: str) -> None:
        with self._lock:
            self._candidates.pop(path, None)

    # ---- startup recovery --------------------------------------------------

    def recover(self) -> None:
        """On launch: prune stale rows, then surface everything that is due.

        Handles the "PC was off when a snooze came due" case and the "file was
        deleted while we were off" case (those are marked MISSING, never shown).
        Delivery goes through the same callback as live events, so the app can
        coalesce a large backlog into the batch Review window.
        """
        self._prune_old()
        for item in self._db.pending_and_due_snoozed(self._now()):
            if not item.exists():
                self._db.set_status(item.id, Status.MISSING)
                continue
            if item.status == Status.SNOOZED:
                self._db.set_status(item.id, Status.PENDING)
                item.status = Status.PENDING
            self._on_ready(item)

    def _prune_old(self) -> None:
        """Keep the database small: drop old resolved/missing rows. KEPT,
        IGNORED and BASELINE are retained forever (they are our 'do not prompt'
        memory)."""
        cutoff = self._now() - self._cfg.retention_days * 86400
        self._db.prune_resolved(
            cutoff, (Status.DELETED, Status.MOVED, Status.MISSING)
        )
