"""Exercise the Qt UI paths under the offscreen platform (no real display)."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
_tmp = tempfile.mkdtemp(prefix="dirwatch-ui-")
os.environ["XDG_CONFIG_HOME"] = str(Path(_tmp) / "config")
os.environ["XDG_DATA_HOME"] = str(Path(_tmp) / "data")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from dirwatch.models import Item, Status
from dirwatch.ui.app import DirwatchApp
from dirwatch.ui.digest import DigestWindow
from dirwatch.ui.popup import Popup, PopupManager
from dirwatch.ui.settings_window import SettingsWindow


def make_item(tmp, name, db):
    f = Path(tmp) / name
    f.write_bytes(b"hello world payload")
    st = f.stat()
    return db.upsert(Item(path=str(f), inode=st.st_ino, size=st.st_size,
                          watch_dir=tmp, status=Status.PENDING, first_seen=0.0))


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    controller = DirwatchApp(app)
    print("OK: DirwatchApp constructed")

    db = controller._db
    work = tempfile.mkdtemp(prefix="dirwatch-files-")

    # 1. Single macOS-style card builds and a decision dismisses it.
    item = make_item(work, "invoice.pdf", db)
    dismissed = []
    popup = Popup(item, controller, dismissed.append)
    popup.present()
    app.processEvents()
    popup._do(controller.keep)
    app.processEvents()
    assert db.get(item.path, item.inode).status == Status.KEPT
    print("OK: card built and Keep recorded")

    # 2. PopupManager shows one at a time, queues the rest.
    mgr = PopupManager(controller)
    items = [make_item(work, f"file_{i}.zip", db) for i in range(3)]
    for it in items:
        mgr.present(it)
    app.processEvents()
    assert mgr._active is not None
    assert len(mgr._queue) == 2, len(mgr._queue)
    assert mgr.pending_count() == 3
    mgr.close_all()
    for it in items:  # resolve so they don't leak into the digest query below
        controller.keep(it)
    print("OK: one card active, rest queued")

    # 3. Digest window lists pending files and bulk-keep clears them.
    empty_called = []
    digest = DigestWindow(db, on_changed=lambda: None, on_empty=lambda: empty_called.append(1))
    batch = [make_item(work, f"batch_{i}.png", db) for i in range(6)]
    digest.refresh()
    app.processEvents()
    assert len(digest._rows) == 6, len(digest._rows)
    digest._bulk("keep")  # no selection -> applies to all
    app.processEvents()
    assert len(digest._rows) == 0, "rows remain after bulk keep"
    assert empty_called, "on_empty not fired when digest emptied"
    for b in batch:
        assert db.get(b.path, b.inode).status == Status.KEPT
    print("OK: digest lists files and bulk-keep works")

    # 4. Digest skips a file deleted on disk (no crash).
    ghost = make_item(work, "ghost.txt", db)
    Path(ghost.path).unlink()
    digest.refresh()
    app.processEvents()
    assert db.get(ghost.path, ghost.inode).status == Status.MISSING
    print("OK: digest marks vanished file MISSING, no crash")

    # 5. Settings window builds and panes switch.
    win = SettingsWindow(controller._cfg, lambda: None)
    app.processEvents()
    for i in range(win._stack.count()):
        win._stack.setCurrentIndex(i)
        app.processEvents()
    assert win._stack.count() == 4
    print("OK: settings window + all 4 panes build")

    # 6. App recover() runs without error on an empty/clean state.
    controller._engine.recover()
    app.processEvents()
    print("OK: recover() runs clean")

    print("\nALL UI SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
