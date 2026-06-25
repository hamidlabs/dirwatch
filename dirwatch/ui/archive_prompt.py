"""When an extracted folder is kept or moved, offer to trash its source archive."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox
from send2trash import send2trash

from ..db import Database
from ..models import Item, Status
from ..util import find_source_archive


def offer_archive_cleanup(parent, db: Database, folder_item: Item) -> None:
    """If `folder_item` is a folder with a matching source archive still on disk,
    ask whether to send that archive to Trash."""
    if not folder_item.is_dir:
        return
    archive = find_source_archive(folder_item.path)
    if archive is None:
        return

    box = QMessageBox(parent)
    box.setWindowTitle("dirwatch")
    box.setIcon(QMessageBox.Icon.Question)
    box.setText(f"Delete the source archive for “{Path(folder_item.path).name}”?")
    box.setInformativeText(f"Move “{archive.name}” to Trash — you've kept the extracted folder.")
    delete_btn = box.addButton("Delete archive", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Keep it", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() is not delete_btn:
        return

    try:
        send2trash(str(archive))
    except Exception:
        return
    existing = db.get_by_path(str(archive))
    if existing is not None:
        db.set_status(existing.id, Status.DELETED)
