"""Filesystem watching via watchdog.

The handler is intentionally dumb: it forwards "something happened at this path"
to a callback. All debouncing, stability checks and decisions live in the
engine, so the watcher has no policy of its own.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

# callback(path: str, watch_dir: str)
Candidate = Callable[[str, str], None]


class _Handler(FileSystemEventHandler):
    def __init__(self, watch_dir: str, on_candidate: Candidate):
        self._watch_dir = watch_dir
        self._on_candidate = on_candidate

    def _emit(self, event: FileSystemEvent, path: str | bytes) -> None:
        if event.is_directory:
            return
        p = path.decode() if isinstance(path, bytes) else path
        # Only react to direct children of the watched dir, not nested trees.
        if Path(p).parent != Path(self._watch_dir):
            return
        self._on_candidate(p, self._watch_dir)

    def on_created(self, event: FileSystemEvent) -> None:
        self._emit(event, event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._emit(event, event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        # e.g. browser renames foo.crdownload -> foo
        self._emit(event, event.dest_path)


class Watcher:
    def __init__(self, on_candidate: Candidate):
        self._on_candidate = on_candidate
        self._observer = Observer()
        self._watches: dict[str, object] = {}
        self._started = False

    def watch(self, directory: Path) -> bool:
        key = str(directory)
        if key in self._watches:
            return True
        if not directory.is_dir():
            return False
        handler = _Handler(key, self._on_candidate)
        self._watches[key] = self._observer.schedule(handler, key, recursive=False)
        return True

    def unwatch(self, directory: Path) -> None:
        key = str(directory)
        watch = self._watches.pop(key, None)
        if watch is not None:
            self._observer.unschedule(watch)

    def watched_dirs(self) -> list[str]:
        return list(self._watches)

    def start(self) -> None:
        if not self._started:
            self._observer.start()
            self._started = True

    def stop(self) -> None:
        if self._started:
            self._observer.stop()
            self._observer.join(timeout=3)
            self._started = False
