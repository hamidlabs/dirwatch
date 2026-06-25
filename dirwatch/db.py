"""SQLite persistence for items, decisions, snoozes and baselines.

Identity is (watch_dir, path, inode). The inode guards against a new, different
file reusing a path we previously resolved: if the inode differs, it is a new
file and should be prompted again.
"""
from __future__ import annotations

import sqlite3
import time
import threading
from pathlib import Path

from .models import Item, Status
from .paths import db_file

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    path         TEXT NOT NULL,
    inode        INTEGER NOT NULL,
    size         INTEGER NOT NULL,
    watch_dir    TEXT NOT NULL,
    status       TEXT NOT NULL,
    first_seen   REAL NOT NULL,
    decided_at   REAL,
    snooze_until REAL,
    is_dir       INTEGER NOT NULL DEFAULT 0,
    UNIQUE(path, inode)
);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_snooze ON items(snooze_until);

CREATE TABLE IF NOT EXISTS baselined_dirs (
    path        TEXT PRIMARY KEY,
    baselined_at REAL NOT NULL
);
"""


class Database:
    def __init__(self, path: Path | None = None):
        self._path = str(path or db_file())
        # check_same_thread=False: the engine (Qt main thread) and tests share one
        # connection; we serialize access with a lock.
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            # Migration for databases created before directory support.
            try:
                self._conn.execute(
                    "ALTER TABLE items ADD COLUMN is_dir INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # column already exists
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- item lookup -------------------------------------------------------

    def _row_to_item(self, row: sqlite3.Row) -> Item:
        return Item(
            id=row["id"],
            path=row["path"],
            inode=row["inode"],
            size=row["size"],
            watch_dir=row["watch_dir"],
            status=Status(row["status"]),
            first_seen=row["first_seen"],
            decided_at=row["decided_at"],
            snooze_until=row["snooze_until"],
            is_dir=bool(row["is_dir"]),
        )

    def get(self, path: str, inode: int) -> Item | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM items WHERE path=? AND inode=?", (path, inode)
            ).fetchone()
        return self._row_to_item(row) if row else None

    def get_by_path(self, path: str) -> Item | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM items WHERE path=? ORDER BY id DESC LIMIT 1", (path,)
            ).fetchone()
        return self._row_to_item(row) if row else None

    def upsert(self, item: Item) -> Item:
        """Insert or update by (path, inode), returning the row with its id."""
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO items (path, inode, size, watch_dir, status,
                                   first_seen, decided_at, snooze_until, is_dir)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(path, inode) DO UPDATE SET
                    size=excluded.size,
                    watch_dir=excluded.watch_dir,
                    status=excluded.status,
                    decided_at=excluded.decided_at,
                    snooze_until=excluded.snooze_until,
                    is_dir=excluded.is_dir
                """,
                (
                    item.path, item.inode, item.size, item.watch_dir,
                    item.status.value, item.first_seen, item.decided_at,
                    item.snooze_until, int(item.is_dir),
                ),
            )
            self._conn.commit()
            if item.id is None:
                row = self._conn.execute(
                    "SELECT id FROM items WHERE path=? AND inode=?",
                    (item.path, item.inode),
                ).fetchone()
                item.id = row["id"]
            else:
                item.id = cur.lastrowid or item.id
        return item

    def set_status(
        self,
        item_id: int,
        status: Status,
        *,
        snooze_until: float | None = None,
        new_path: str | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE items
                   SET status=?, decided_at=?, snooze_until=?,
                       path=COALESCE(?, path)
                 WHERE id=?
                """,
                (status.value, time.time(), snooze_until, new_path, item_id),
            )
            self._conn.commit()

    def due_snoozed(self, now: float | None = None) -> list[Item]:
        now = now if now is not None else time.time()
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM items WHERE status=? AND snooze_until<=?",
                (Status.SNOOZED.value, now),
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def pending_and_due_snoozed(self, now: float | None = None) -> list[Item]:
        """Everything that should be in front of the user right now."""
        now = now if now is not None else time.time()
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM items
                 WHERE status=?
                    OR (status=? AND snooze_until<=?)
                 ORDER BY first_seen ASC
                """,
                (Status.PENDING.value, Status.SNOOZED.value, now),
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def prune_resolved(self, older_than: float, statuses: tuple[Status, ...]) -> int:
        """Delete resolved rows decided before `older_than`. Returns count."""
        placeholders = ",".join("?" for _ in statuses)
        with self._lock:
            cur = self._conn.execute(
                f"DELETE FROM items WHERE status IN ({placeholders}) "
                "AND COALESCE(decided_at, first_seen) < ?",
                (*[s.value for s in statuses], older_than),
            )
            self._conn.commit()
            return cur.rowcount

    def by_status(self, *statuses: Status) -> list[Item]:
        placeholders = ",".join("?" for _ in statuses)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM items WHERE status IN ({placeholders}) "
                "ORDER BY first_seen DESC",
                tuple(s.value for s in statuses),
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    # ---- baselining --------------------------------------------------------

    def is_dir_baselined(self, path: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM baselined_dirs WHERE path=?", (path,)
            ).fetchone()
        return row is not None

    def mark_dir_baselined(self, path: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO baselined_dirs (path, baselined_at) "
                "VALUES (?, ?)",
                (path, time.time()),
            )
            self._conn.commit()
