#!/usr/bin/env bash
# Build a self-contained dirwatch AppImage (Linux x86_64).
#
# Strategy: PyInstaller freezes the app + PySide6 into a one-folder bundle,
# then appimagetool wraps it. No system Python needed on the target machine.
#
# Requirements (build host): python3, pip, internet (to fetch appimagetool once),
# and FUSE *or* we fall back to appimagetool --appimage-extract-and-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BUILD="$ROOT/build/appimage"
APPDIR="$BUILD/dirwatch.AppDir"
VENV="$BUILD/venv"
ARCH="${ARCH:-x86_64}"
OUT="$ROOT/dist/dirwatch-${ARCH}.AppImage"

echo "==> Clean build dir"
rm -rf "$BUILD"
mkdir -p "$BUILD" "$ROOT/dist"

echo "==> Create build venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip wheel >/dev/null
"$VENV/bin/pip" install . pyinstaller >/dev/null

echo "==> Freeze with PyInstaller"
"$VENV/bin/pyinstaller" --noconfirm --clean --windowed \
    --name dirwatch \
    --collect-all PySide6 \
    --collect-all watchdog \
    --collect-all send2trash \
    --distpath "$BUILD/dist" --workpath "$BUILD/work" --specpath "$BUILD" \
    packaging/dirwatch-entry.py

echo "==> Assemble AppDir"
mkdir -p "$APPDIR/usr/bin"
cp -r "$BUILD/dist/dirwatch/." "$APPDIR/usr/bin/"

# Icon (render PNG from the app's own icon) + desktop file
QT_QPA_PLATFORM=offscreen "$VENV/bin/python" packaging/make_icon.py "$APPDIR/dirwatch.png" 256
cp "$APPDIR/dirwatch.png" "$APPDIR/.DirIcon"
install -Dm644 packaging/dirwatch.desktop "$APPDIR/dirwatch.desktop"
install -Dm644 packaging/dirwatch.svg \
    "$APPDIR/usr/share/icons/hicolor/scalable/apps/dirwatch.svg"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="$HERE/usr/bin:$PATH"
exec "$HERE/usr/bin/dirwatch" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "==> Fetch appimagetool if needed"
TOOL="$BUILD/appimagetool"
if ! command -v appimagetool >/dev/null 2>&1; then
    curl -fsSL -o "$TOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
    chmod +x "$TOOL"
    APPIMAGETOOL="$TOOL"
else
    APPIMAGETOOL="$(command -v appimagetool)"
fi

echo "==> Build AppImage"
# --appimage-extract-and-run avoids needing FUSE on the build host.
ARCH="$ARCH" "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$OUT" \
    || ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$OUT"

echo "==> Done: $OUT"
