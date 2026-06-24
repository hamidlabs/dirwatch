.PHONY: help venv run test install uninstall appimage clean

PREFIX ?= $(HOME)/.local
PY ?= python3

help:
	@echo "dirwatch make targets:"
	@echo "  make venv      - create .venv and install the app (editable) + deps"
	@echo "  make run       - run dirwatch from the venv"
	@echo "  make test      - run the headless smoke tests"
	@echo "  make install   - install into $(PREFIX) (pipx-style) + desktop entry & icon"
	@echo "  make uninstall - remove the desktop entry, icon and autostart entry"
	@echo "  make appimage  - build a portable dist/dirwatch-x86_64.AppImage"
	@echo "  make clean     - remove build artifacts"

venv:
	$(PY) -m venv .venv
	.venv/bin/pip install --upgrade pip >/dev/null
	.venv/bin/pip install -e .

run:
	.venv/bin/dirwatch

test:
	.venv/bin/python scripts/smoke_engine.py
	QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/smoke_ui.py

install:
	$(PY) -m pip install --user .
	install -Dm644 packaging/dirwatch.desktop $(PREFIX)/share/applications/dirwatch.desktop
	install -Dm644 packaging/dirwatch.svg $(PREFIX)/share/icons/hicolor/scalable/apps/dirwatch.svg
	-update-desktop-database $(PREFIX)/share/applications 2>/dev/null || true
	@echo "Installed. Launch from your app menu or run: dirwatch"

uninstall:
	rm -f $(PREFIX)/share/applications/dirwatch.desktop
	rm -f $(PREFIX)/share/icons/hicolor/scalable/apps/dirwatch.svg
	rm -f $(HOME)/.config/autostart/dirwatch.desktop
	@echo "Removed desktop entry, icon and autostart entry (pip package left intact)."

appimage:
	bash packaging/build-appimage.sh

clean:
	rm -rf build dist *.egg-info .venv/__pycache__
	find dirwatch -name __pycache__ -type d -prune -exec rm -rf {} +
