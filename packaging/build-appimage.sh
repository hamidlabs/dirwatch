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

echo "==> Freeze with PyInstaller (lean: only QtCore/Gui/Widgets)"
# We deliberately do NOT --collect-all PySide6: that pulls QtWebEngine, QML,
# Quick, Multimedia, 3D, Charts, etc. (150MB+ we never use). The PySide6 hook
# bundles only the imported modules plus required platform plugins.
EXCLUDES=(
    PySide6.QtWebEngineCore PySide6.QtWebEngineWidgets PySide6.QtWebEngineQuick
    PySide6.QtQml PySide6.QtQuick PySide6.QtQuick3D PySide6.QtQuickWidgets
    PySide6.QtQuickControls2 PySide6.QtQml.QtQmlNetwork
    PySide6.Qt3DCore PySide6.Qt3DRender PySide6.Qt3DExtras PySide6.Qt3DInput
    PySide6.Qt3DLogic PySide6.Qt3DAnimation
    PySide6.QtCharts PySide6.QtDataVisualization PySide6.QtGraphs
    PySide6.QtMultimedia PySide6.QtMultimediaWidgets PySide6.QtSpatialAudio
    PySide6.QtPdf PySide6.QtPdfWidgets PySide6.QtSql PySide6.QtTest
    PySide6.QtBluetooth PySide6.QtNfc PySide6.QtSensors PySide6.QtSerialPort
    PySide6.QtSerialBus PySide6.QtWebSockets PySide6.QtWebChannel
    PySide6.QtPositioning PySide6.QtRemoteObjects PySide6.QtScxml
    PySide6.QtTextToSpeech PySide6.QtHelp PySide6.QtDesigner PySide6.QtUiTools
    PySide6.QtNetworkAuth PySide6.QtOpenGLWidgets PySide6.QtOpenGL
    tkinter unittest pydoc_data
)
EXFLAGS=()
for m in "${EXCLUDES[@]}"; do EXFLAGS+=(--exclude-module "$m"); done

"$VENV/bin/pyinstaller" --noconfirm --clean --windowed --strip \
    --name dirwatch \
    --collect-all watchdog \
    --collect-all send2trash \
    "${EXFLAGS[@]}" \
    --distpath "$BUILD/dist" --workpath "$BUILD/work" --specpath "$BUILD" \
    packaging/dirwatch-entry.py

echo "==> Prune unused Qt libraries, plugins and data"
QT="$BUILD/dist/dirwatch/_internal/PySide6/Qt"
if [ -d "$QT" ]; then
    rm -f "$QT"/lib/libQt6WebEngine* "$QT"/lib/libQt6Quick* "$QT"/lib/libQt6Qml* \
          "$QT"/lib/libQt63D* "$QT"/lib/libQt6Charts* "$QT"/lib/libQt6DataVisualization* \
          "$QT"/lib/libQt6Graphs* "$QT"/lib/libQt6Multimedia* "$QT"/lib/libQt6SpatialAudio* \
          "$QT"/lib/libQt6Pdf* "$QT"/lib/libQt6Designer* "$QT"/lib/libQt6Test* \
          "$QT"/lib/libQt6Sql* "$QT"/lib/libQt6Bluetooth* "$QT"/lib/libQt6Nfc* \
          "$QT"/lib/libQt6Sensors* "$QT"/lib/libQt6SerialPort* "$QT"/lib/libQt6SerialBus* \
          "$QT"/lib/libQt6WebSockets* "$QT"/lib/libQt6WebChannel* "$QT"/lib/libQt6Positioning* \
          "$QT"/lib/libQt6RemoteObjects* "$QT"/lib/libQt6Scxml* "$QT"/lib/libQt6TextToSpeech* \
          "$QT"/lib/libQt6Help* "$QT"/lib/libQt6Quick3D* "$QT"/lib/libQt6Pdf* 2>/dev/null || true
    rm -rf "$QT"/qml "$QT"/translations "$QT"/resources \
           "$QT"/plugins/sqldrivers "$QT"/plugins/multimedia "$QT"/plugins/assetimporters \
           "$QT"/plugins/qmltooling "$QT"/plugins/designer "$QT"/plugins/sensors \
           "$QT"/plugins/position "$QT"/plugins/texttospeech "$QT"/plugins/webview \
           "$QT"/plugins/sceneparsers "$QT"/plugins/renderplugins 2>/dev/null || true
    find "$QT" -name 'QtWebEngineProcess*' -delete 2>/dev/null || true
fi

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
