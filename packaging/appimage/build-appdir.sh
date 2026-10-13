#!/usr/bin/env bash
# Build Doremi.AppDir from the verified PyInstaller onedir (F0B-3B).
#
# Usage:
#   packaging/appimage/build-appdir.sh [DIST_DIR] [APPDIR]
#
# Defaults: DIST_DIR=dist/Doremi, APPDIR=Doremi.AppDir
# Inputs (must exist, built from the SAME commit by doremi-linux.spec):
#   dist/Doremi/Doremi          ELF onedir executable
#   dist/Doremi/_internal/      == sys._MEIPASS (Qt, vlc_libs, doremi data, ...)
#   dist/Doremi/doremi.sh       verified portable launcher
#   packaging/appimage/AppRun
#   packaging/appimage/doremi.desktop
#   assets/Doremi.png
#
# Output layout (AppImage standard, PyInstaller onedir preserved intact):
#   Doremi.AppDir/
#     AppRun                    executable, invokes usr/bin/doremi
#     doremi.desktop            validated desktop entry
#     doremi.png                1080x1080 icon
#     .DirIcon -> doremi.png    symlink required by the spec
#     usr/bin/Doremi            copy of the onedir exe (permissions kept)
#     usr/bin/doremi            copy of doremi.sh (executable)
#     usr/bin/_internal/        full copy of dist _internal (permissions kept)
#
# Deliberately does NOT:
#   - run linuxdeploy or bundle a second copy of Qt/VLC,
#   - copy host glibc or GPU drivers,
#   - strip plugins or libraries to save megabytes.
set -euo pipefail

DIST_DIR="${1:-dist/Doremi}"
APPDIR="${2:-Doremi.AppDir}"
SRC_APPIMAGE_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO_ROOT="$(cd "$SRC_APPIMAGE_DIR/../.." && pwd)"

EXE="$DIST_DIR/Doremi"
INTERNAL="$DIST_DIR/_internal"
LAUNCHER_SRC="$DIST_DIR/doremi.sh"
APPRUN_SRC="$REPO_ROOT/packaging/appimage/AppRun"
DESKTOP_SRC="$REPO_ROOT/packaging/appimage/doremi.desktop"
ICON_SRC="$REPO_ROOT/assets/Doremi.png"

fail() { echo "build-appdir: $*" >&2; exit 1; }

test -x "$REPO_ROOT/$EXE" || test -x "$EXE" || fail "missing executable: $EXE (build doremi-linux.spec first)"
test -d "$REPO_ROOT/$INTERNAL" || test -d "$INTERNAL" || fail "missing _internal dir: $INTERNAL"
# Allow both relative and absolute inputs.
if [[ "$DIST_DIR" != /* ]]; then DIST_DIR="$REPO_ROOT/$DIST_DIR"; fi
if [[ "$APPDIR" != /* ]]; then APPDIR="$REPO_ROOT/$APPDIR"; fi
if [[ ! -x "$DIST_DIR/Doremi" ]]; then fail "missing executable: $DIST_DIR/Doremi"; fi
if [[ ! -d "$DIST_DIR/_internal" ]]; then fail "missing _internal dir: $DIST_DIR/_internal"; fi
[[ -f "$DIST_DIR/doremi.sh" ]] || fail "missing launcher: $DIST_DIR/doremi.sh (copy packaging/linux/doremi.sh into dist first)"
[[ -f "$SRC_APPIMAGE_DIR/AppRun" ]] || fail "missing $SRC_APPIMAGE_DIR/AppRun"
[[ -f "$SRC_APPIMAGE_DIR/doremi.desktop" ]] || fail "missing $SRC_APPIMAGE_DIR/doremi.desktop"
[[ -f "$REPO_ROOT/assets/Doremi.png" ]] || fail "missing $REPO_ROOT/assets/Doremi.png"

echo "build-appdir: DIST=$DIST_DIR APPDIR=$APPDIR"

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

# 1. Executable + _internal preserved intact (permissions kept with cp -a).
cp -a "$DIST_DIR/Doremi" "$APPDIR/usr/bin/Doremi"
cp -a "$DIST_DIR/_internal" "$APPDIR/usr/bin/_internal"
chmod +x "$APPDIR/usr/bin/Doremi"

# 2. Launcher (verified doremi.sh) as usr/bin/doremi.
cp -a "$DIST_DIR/doremi.sh" "$APPDIR/usr/bin/doremi"
chmod +x "$APPDIR/usr/bin/doremi"

# 3. AppRun at the AppDir root.
cp -a "$SRC_APPIMAGE_DIR/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"

# 4. Desktop + icon + .DirIcon.
cp -a "$SRC_APPIMAGE_DIR/doremi.desktop" "$APPDIR/doremi.desktop"
cp -a "$REPO_ROOT/assets/Doremi.png" "$APPDIR/doremi.png"
ln -sf doremi.png "$APPDIR/.DirIcon"

# 4b. Licenses (same as the portable + AppImage runtime addendum).
mkdir -p "$APPDIR/usr/share/doc/doremi"
cp -a "$REPO_ROOT/LICENSE" "$APPDIR/usr/share/doc/doremi/LICENSE.txt"
cp -a "$REPO_ROOT/packaging/linux/THIRD-PARTY-NOTICES.txt" "$APPDIR/usr/share/doc/doremi/THIRD-PARTY-NOTICES.txt"
cp -a "$SRC_APPIMAGE_DIR/APPIMAGE-NOTICES.txt" "$APPDIR/usr/share/doc/doremi/APPIMAGE-NOTICES.txt"

# 5. Sanity checks (mirrors F0B-3A bundle checks, relocated under usr/bin).
checks=(
  "$APPDIR/AppRun"
  "$APPDIR/doremi.desktop"
  "$APPDIR/doremi.png"
  "$APPDIR/.DirIcon"
  "$APPDIR/usr/bin/Doremi"
  "$APPDIR/usr/bin/doremi"
  "$APPDIR/usr/share/doc/doremi/LICENSE.txt"
  "$APPDIR/usr/share/doc/doremi/THIRD-PARTY-NOTICES.txt"
  "$APPDIR/usr/share/doc/doremi/APPIMAGE-NOTICES.txt"
  "$APPDIR/usr/bin/_internal/doremi/ui/qml/MainShell.qml"
  "$APPDIR/usr/bin/_internal/doremi/ui/qml/Doremi/qmldir"
  "$APPDIR/usr/bin/_internal/doremi/assets/fonts/Inter-Regular.ttf"
  "$APPDIR/usr/bin/_internal/doremi/locales/es.json"
  "$APPDIR/usr/bin/_internal/doremi/db/migrations/env.py"
  "$APPDIR/usr/bin/_internal/assets/Doremi.png"
  "$APPDIR/usr/bin/_internal/vlc_libs/libvlc.so.5"
  "$APPDIR/usr/bin/_internal/vlc_libs/plugins"
)
for p in "${checks[@]}"; do
  if [[ -e "$p" ]]; then
    echo "  ok: ${p#$APPDIR/}"
  else
    fail "missing AppDir entry: $p"
  fi
done
test -x "$APPDIR/AppRun" || fail "AppRun not executable"
test -x "$APPDIR/usr/bin/Doremi" || fail "usr/bin/Doremi not executable"
test -x "$APPDIR/usr/bin/doremi" || fail "usr/bin/doremi not executable"

# Rust extension must be next to the bridge (same check as portable).
rust_ext=$(ls "$APPDIR/usr/bin/_internal/doremi/native_rs/"*.so 2>/dev/null | head -1 || true)
[[ -n "$rust_ext" ]] || fail "missing Rust extension under _internal/doremi/native_rs/"
echo "  ok: rust ext ${rust_ext#$APPDIR/} ($(stat -c%s "$rust_ext") B)"

# Qt platform plugins + QML resources must be present (no second copy via deploy tools).
for qp in \
  "$APPDIR/usr/bin/_internal/PySide6/Qt/plugins/platforms/libqxcb.so" \
  "$APPDIR/usr/bin/_internal/PySide6/Qt/plugins/platforms/libqoffscreen.so" \
  "$APPDIR/usr/bin/_internal/PySide6/Qt/plugins/platforms/libqwayland.so" \
  "$APPDIR/usr/bin/_internal/PySide6/Qt/qml/QtQuick"; do
  [[ -e "$qp" ]] || fail "missing Qt bundle entry: ${qp#$APPDIR/}"
  echo "  ok: ${qp#$APPDIR/}"
done

qml_count=$(find "$APPDIR/usr/bin/_internal/doremi/ui/qml" -name '*.qml' | wc -l)
echo "  qml files: $qml_count"
echo "  AppDir MB: $(du -sm "$APPDIR" | cut -f1)"
echo "  AppDir files: $(find "$APPDIR" -type f | wc -l)"
echo "build-appdir: OK -> $APPDIR"
