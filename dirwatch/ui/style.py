"""macOS-alert-flavored stylesheet: centered card, big icon, bottom buttons."""

from PySide6.QtGui import QColor, QPalette


def apply_light_theme(app) -> None:
    """Force a consistent light, mac-like look regardless of the user's system
    Qt theme (otherwise a dark system palette bleeds through opaque windows)."""
    app.setStyle("Fusion")
    p = QPalette()
    window = QColor("#f5f5f7")
    text = QColor("#1d1d1f")
    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor("#f0f0f3"))
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, QColor("#ececec"))
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8a8a8e"))
    p.setColor(QPalette.ColorRole.Highlight, QColor("#007aff"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.Link, QColor("#007aff"))
    app.setPalette(p)


QSS = """
#card {
    background-color: #ececec;
    border: 1px solid rgba(0,0,0,0.10);
    border-radius: 14px;
}
#title {
    color: #1d1d1f;
    font-size: 16px;
    font-weight: 700;
}
#message {
    color: #4b4b4f;
    font-size: 13px;
}
#meta {
    color: #8a8a8e;
    font-size: 12px;
}
#iconBadge {
    color: white;
    font-size: 20px;
    font-weight: 800;
    border-radius: 18px;
}

/* Primary blue button (the default action) */
QPushButton#primary {
    background-color: #007aff;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#primary:hover { background-color: #0a6ee0; }
QPushButton#primary:pressed { background-color: #0a5fc0; }

/* Neutral filled button */
QPushButton#secondary {
    background-color: #dcdce0;
    color: #1d1d1f;
    border: none;
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#secondary:hover { background-color: #d2d2d7; }
QPushButton#secondary:pressed { background-color: #c6c6cc; }

/* Subtle text/link-style buttons for the lesser actions */
QPushButton#link {
    background: transparent;
    color: #007aff;
    border: none;
    font-size: 12px;
    padding: 4px 8px;
}
QPushButton#link:hover { color: #0a5fc0; text-decoration: underline; }

QPushButton#linkDanger {
    background: transparent;
    color: #e5484d;
    border: none;
    font-size: 12px;
    padding: 4px 8px;
}
QPushButton#linkDanger:hover { color: #c0322f; text-decoration: underline; }

#dot { color: #c4c4c8; font-size: 12px; }

QMenu {
    background-color: #ffffff;
    border: 1px solid rgba(0,0,0,0.12);
    border-radius: 10px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 22px;
    border-radius: 6px;
    font-size: 13px;
    color: #1d1d1f;
}
QMenu::item:selected { background-color: #007aff; color: white; }

/* ---- Review / digest window ---------------------------------------- */
#window { background-color: #f5f5f7; border-radius: 16px; }
#windowTitle { color: #1d1d1f; font-size: 18px; font-weight: 700; }
#windowSub { color: #8a8a8e; font-size: 13px; }

QScrollArea#rowScroll { border: none; background: #f5f5f7; }
QWidget#rowHost { background: #f5f5f7; }

#row {
    background-color: #ffffff;
    border: 1px solid rgba(0,0,0,0.07);
    border-radius: 12px;
}
#row:hover { background-color: #fbfbfd; }
#rowBadge { color: white; font-size: 13px; font-weight: 800; border-radius: 11px; }
#rowName { color: #1d1d1f; font-size: 14px; font-weight: 600; }
#rowMeta { color: #8a8a8e; font-size: 12px; }

QPushButton#mini {
    background-color: #f0f0f3;
    color: #1d1d1f;
    border: none;
    border-radius: 7px;
    padding: 6px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#mini:hover { background-color: #e6e6ea; }
QPushButton#miniPrimary {
    background-color: #007aff; color: white; border: none;
    border-radius: 7px; padding: 6px 6px; font-size: 12px; font-weight: 600;
}
QPushButton#miniPrimary:hover { background-color: #0a6ee0; }
QPushButton#miniDanger {
    background-color: #ffffff; color: #e5484d;
    border: 1px solid rgba(229,72,77,0.30);
    border-radius: 7px; padding: 6px 6px; font-size: 12px; font-weight: 600;
}
QPushButton#miniDanger:hover { background-color: #fdecec; }

#bulkBar {
    background-color: #ececef;
    border-top: 1px solid rgba(0,0,0,0.08);
    border-bottom-left-radius: 16px;
    border-bottom-right-radius: 16px;
}

QCheckBox { color: #4b4b4f; font-size: 13px; spacing: 8px; }
QCheckBox::indicator {
    width: 18px; height: 18px; border-radius: 5px;
    border: 1px solid rgba(0,0,0,0.25); background: white;
}
QCheckBox::indicator:checked {
    background: #007aff; border: 1px solid #007aff;
    image: none;
}

/* ---- Settings window ---------------------------------------------- */
#headerBar {
    background-color: #ececef;
    border-bottom: 1px solid rgba(0,0,0,0.10);
}
#headerTitle { color: #1d1d1f; font-size: 13px; font-weight: 600; }
#sidebar { background-color: #ececef; border-right: 1px solid rgba(0,0,0,0.08); }
QPushButton#navItem {
    background: transparent; color: #1d1d1f; border: none;
    border-radius: 8px; padding: 10px 14px; font-size: 14px; text-align: left;
}
QPushButton#navItem:hover { background-color: rgba(0,0,0,0.05); }
QPushButton#navItem:checked { background-color: #007aff; color: white; font-weight: 600; }

#pane { background-color: #f5f5f7; }
#sectionTitle { color: #1d1d1f; font-size: 20px; font-weight: 700; }
#group {
    background-color: #ffffff;
    border: 1px solid rgba(0,0,0,0.07);
    border-radius: 12px;
}
#groupLabel { color: #1d1d1f; font-size: 14px; font-weight: 600; }
#groupHint { color: #8a8a8e; font-size: 12px; }

QPushButton#cta {
    background-color: #007aff; color: white; border: none;
    border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 600;
}
QPushButton#cta:hover { background-color: #0a6ee0; }
QPushButton#ctaGhost {
    background-color: #e6e6ea; color: #1d1d1f; border: none;
    border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 600;
}
QPushButton#ctaGhost:hover { background-color: #dcdce0; }

QListWidget#folders {
    background: #ffffff; border: 1px solid rgba(0,0,0,0.07);
    border-radius: 10px; padding: 4px; font-size: 13px;
}
QListWidget#folders::item { padding: 8px; border-radius: 6px; }
QListWidget#folders::item:selected { background: #007aff; color: white; }

QSpinBox {
    background: white; border: 1px solid rgba(0,0,0,0.15);
    border-radius: 7px; padding: 5px 8px; font-size: 13px; min-width: 70px;
}

#statusPill { font-size: 12px; font-weight: 600; border-radius: 9px; padding: 4px 10px; }
"""
