"""Headless test of the engine/db/actions logic (no Qt)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dirwatch import actions
from dirwatch.config import Config, WatchedDir
from dirwatch.db import Database
from dirwatch.engine import Engine
from dirwatch.models import Status


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, secs):
        self.t += secs


def main():
    tmp = Path(tempfile.mkdtemp(prefix="dirwatch-test-"))
    watch = tmp / "Downloads"
    watch.mkdir()
    db = Database(tmp / "test.db")
    clock = Clock()
    cfg = Config(watched=[WatchedDir(str(watch))], debounce_seconds=4)

    delivered = []
    eng = Engine(cfg, db, delivered.append, clock=clock)

    def settle(path):
        """Mimic a finished file: first tick records size, second settles it."""
        eng.note_candidate(str(path), str(watch))
        eng.tick()
        clock.advance(cfg.debounce_seconds + 1)
        eng.tick()

    # Pre-existing file should be baselined, never delivered.
    (watch / "old.txt").write_text("already here")
    eng.baseline_dir(watch)
    assert db.is_dir_baselined(str(watch)), "dir not baselined"

    # A new download arrives and grows over two ticks, then settles.
    f = watch / "report.pdf"
    f.write_bytes(b"x" * 100)
    eng.note_candidate(str(f), str(watch))

    eng.tick()                      # first sight: record size, start timer
    assert not delivered, "delivered too early"
    f.write_bytes(b"x" * 500)       # still downloading -> size changed
    clock.advance(2)
    eng.tick()                      # size changed, reset timer
    assert not delivered, "delivered while still growing"
    clock.advance(5)                # now stable past debounce
    eng.tick()
    assert len(delivered) == 1, f"expected 1 delivered, got {len(delivered)}"
    item = delivered[0]
    assert item.status == Status.PENDING
    assert item.name == "report.pdf"
    print("OK: new file delivered after settling")

    # The baselined file, if re-noticed, is not delivered.
    eng.note_candidate(str(watch / "old.txt"), str(watch))
    clock.advance(10)
    eng.tick()
    assert len(delivered) == 1, "baselined file was re-delivered"
    print("OK: baselined file not re-prompted")

    # Snooze, then it wakes. (Set snooze_until on the fake clock directly, since
    # actions.snooze uses real wall-clock time which this test does not.)
    db.set_status(item.id, Status.SNOOZED, snooze_until=clock() + 30)
    refreshed = db.get(item.path, item.inode)
    assert refreshed.status == Status.SNOOZED
    clock.advance(20)
    eng.tick()
    assert len(delivered) == 1, "woke too early"
    clock.advance(15)               # past snooze_until
    eng.tick()
    assert len(delivered) == 2, "snoozed item did not wake"
    print("OK: snooze waking works")

    # Keep is sticky.
    actions.keep(db, item)
    assert db.get(item.path, item.inode).status == Status.KEPT
    print("OK: keep recorded")

    # Delete sends to trash and records.
    g = watch / "junk.zip"
    g.write_bytes(b"junk")
    settle(g)
    g_item = delivered[-1]
    assert g_item.name == "junk.zip"
    actions.delete(db, g_item)
    assert db.get(g_item.path, g_item.inode).status == Status.DELETED
    assert not g.exists(), "file not removed from folder"
    print("OK: delete to trash works")

    # Move relocates and records the new path.
    h = watch / "photo.png"
    h.write_bytes(b"img")
    settle(h)
    h_item = delivered[-1]
    dest = tmp / "Pictures"
    target = actions.move(db, h_item, dest)
    assert target.exists(), "moved file missing at destination"
    assert not h.exists(), "moved file still at source"
    moved_row = db.get(str(target), h_item.inode)
    assert moved_row is not None and moved_row.status == Status.MOVED, "move not recorded"
    print("OK: move works")

    # Temp/partial files are ignored.
    part = watch / "big.iso.crdownload"
    part.write_bytes(b"partial")
    settle(part)
    assert all(d.name != "big.iso.crdownload" for d in delivered), "temp file prompted"
    print("OK: partial download ignored")

    # Directories (e.g. an extracted archive) are triaged like files.
    folder = watch / "extracted-project"
    folder.mkdir()
    (folder / "readme.txt").write_bytes(b"hello")
    (folder / "data.bin").write_bytes(b"x" * 1000)
    delivered.clear()
    settle(folder)
    assert delivered and delivered[-1].name == "extracted-project", "folder not triaged"
    assert delivered[-1].is_dir is True, "folder not marked is_dir"
    assert delivered[-1].size >= 1000, "folder size should sum its contents"
    print("OK: new folder is triaged (is_dir, total size)")

    # A folder still being written (extraction in progress) keeps resetting the
    # settle timer until its contents stop changing.
    f2 = watch / "downloading-set"
    f2.mkdir()
    eng.note_candidate(str(f2), str(watch))
    eng.tick()                                   # snapshot: empty
    (f2 / "part1").write_bytes(b"x" * 10)
    clock.advance(cfg.debounce_seconds + 1)
    eng.tick()                                   # changed -> reset
    before = len(delivered)
    (f2 / "part2").write_bytes(b"x" * 10)
    clock.advance(cfg.debounce_seconds + 1)
    eng.tick()                                   # changed again -> reset
    assert len(delivered) == before, "folder delivered while still being written"
    clock.advance(cfg.debounce_seconds + 1)
    eng.tick()                                   # stable -> delivered
    assert len(delivered) == before + 1 and delivered[-1].name == "downloading-set"
    print("OK: folder settles only after it stops changing")

    # Keep works on a folder item too.
    actions.keep(db, delivered[-1])
    assert db.get(delivered[-1].path, delivered[-1].inode).status == Status.KEPT
    print("OK: keep works on a folder")

    # A file held open by another process is not prompted until it's closed.
    import os as _os
    busy = watch / "watching.mp4"
    busy.write_bytes(b"x" * 2000)
    fh = open(busy, "rb")            # simulate a media player holding it open
    delivered.clear()
    eng.note_candidate(str(busy), str(watch))
    eng.tick()
    clock.advance(cfg.debounce_seconds + 1)
    eng.tick()
    assert all(d.name != "watching.mp4" for d in delivered), "prompted while in use"
    fh.close()                      # user closes the player
    clock.advance(cfg.debounce_seconds + 1)
    eng.tick()
    assert any(d.name == "watching.mp4" for d in delivered), "not prompted after closed"
    print("OK: in-use file deferred until closed")

    # Archive linking: folder name matches a sibling archive.
    from dirwatch.util import find_source_archive, archive_base, is_archive
    assert archive_base("Foo.tar.gz") == "Foo" and is_archive("Foo.zip")
    (watch / "Bundle.zip").write_bytes(b"zip")
    (watch / "Bundle").mkdir()
    found = find_source_archive(str(watch / "Bundle"))
    assert found is not None and found.name == "Bundle.zip", "source archive not linked"
    print("OK: archive linked to extracted folder")

    # Snoozed files must NOT appear in the prompt for newly-arrived files, and
    # each snooze fires on its own independent schedule.
    delivered.clear()
    a = watch / "snoozed_A.txt"; a.write_bytes(b"a"); settle(a)
    item_a = delivered[-1]
    db.set_status(item_a.id, Status.SNOOZED, snooze_until=clock() + 7200)  # 2 hours
    b = watch / "new_B.txt"; b.write_bytes(b"b"); settle(b)
    pending_names = [i.name for i in db.by_status(Status.PENDING)]
    assert "new_B.txt" in pending_names
    assert "snoozed_A.txt" not in pending_names, "snoozed file leaked into new prompt"
    clock.advance(3600); eng.tick()                      # 1h later: A still asleep
    assert db.get(item_a.path, item_a.inode).status == Status.SNOOZED, "woke early"
    clock.advance(3700); eng.tick()                      # past its own 2h mark
    assert db.get(item_a.path, item_a.inode).status == Status.PENDING, "missed its time"
    print("OK: snoozed files excluded from new prompts; schedules independent")

    # Recovery after a restart: a snoozed-and-now-due file should resurface,
    # and a pending file whose file was deleted must NOT crash or be shown.
    delivered.clear()
    due = watch / "due.txt"
    due.write_bytes(b"due")
    settle(due)
    due_item = delivered[-1]
    db.set_status(due_item.id, Status.SNOOZED, snooze_until=clock() - 5)  # already due

    gone = watch / "ghost.txt"
    gone.write_bytes(b"boo")
    settle(gone)
    gone_item = delivered[-1]
    gone.unlink()  # user deletes it from the file manager while we're "off"

    delivered.clear()
    eng.recover()
    names = [d.name for d in delivered]
    assert "due.txt" in names, "due snooze not recovered"
    assert "ghost.txt" not in names, "deleted file was surfaced (should be skipped)"
    assert db.get(gone_item.path, gone_item.inode).status == Status.MISSING
    print("OK: recover wakes due snoozes and skips deleted files")

    # Retention prune removes old resolved/missing rows but keeps baseline.
    # (Insert an aged DELETED row directly so its timestamp uses the fake clock.)
    from dirwatch.models import Item as _Item
    aged = db.upsert(_Item(
        path=str(watch / "ancient.bin"), inode=987654, size=1,
        watch_dir=str(watch), status=Status.DELETED,
        first_seen=clock() - 100 * 86400,
    ))
    eng._prune_old()  # cutoff = now - 30d; aged row is 100d old -> pruned
    assert db.get(aged.path, aged.inode) is None, "old DELETED row not pruned"
    assert any(i.name == "old.txt" for i in db.by_status(Status.BASELINE)), \
        "baseline row wrongly pruned"
    print("OK: retention prunes resolved rows, keeps baseline")

    db.close()
    print("\nALL ENGINE TESTS PASSED")


if __name__ == "__main__":
    main()
