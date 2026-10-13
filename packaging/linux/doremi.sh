#!/usr/bin/env bash
# Doremi portable launcher (Linux x86_64).
#
# Sets up the bundle library paths WITHOUT overwriting the user's environment,
# works from any working directory, and execs the PyInstaller onedir binary.
# No root required. User data always lives in XDG dirs, never inside the bundle.
#
# Layouts supported (both keep the PyInstaller exe next to its _internal/):
#   1. Flat (tar root IS the onedir): ./Doremi + ./_internal/ + ./doremi.sh
#   2. Nested: ./Doremi/Doremi + ./Doremi/_internal/ with this script at root
set -euo pipefail

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

if [[ -x "$HERE/Doremi" && -d "$HERE/_internal" ]]; then
    APPDIR="$HERE"
elif [[ -x "$HERE/Doremi/Doremi" ]]; then
    APPDIR="$HERE/Doremi"
else
    echo "doremi.sh: cannot locate the Doremi executable (tried $HERE/Doremi and $HERE/Doremi/Doremi)" >&2
    exit 1
fi

# _MEIPASS equivalent: PyInstaller 6 keeps everything under _internal/.
if [[ -d "$APPDIR/_internal/vlc_libs" ]]; then
    VLCDIR="$APPDIR/_internal/vlc_libs"
elif [[ -d "$APPDIR/vlc_libs" ]]; then
    VLCDIR="$APPDIR/vlc_libs"
else
    VLCDIR=""
fi

if [[ -n "$VLCDIR" ]]; then
    # Prepend (never overwrite) so bundled libs win without hiding the system.
    case ":${LD_LIBRARY_PATH:-}:" in
        *":$VLCDIR:"*) ;;
        *) export LD_LIBRARY_PATH="$VLCDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ;;
    esac
    # python-vlc binds its library at import time via find_library() (ldconfig),
    # which ignores the bundle: pin the bundled file deterministically.
    if [[ -z "${PYTHON_VLC_LIB_PATH:-}" ]]; then
        for _lib in libvlc.so.5 libvlc.so; do
            if [[ -f "$VLCDIR/$_lib" ]]; then
                export PYTHON_VLC_LIB_PATH="$VLCDIR/$_lib"
                break
            fi
        done
    fi
    # libVLC loads its plugins from VLC_PLUGIN_PATH at runtime.
    if [[ -z "${VLC_PLUGIN_PATH:-}" && -d "$VLCDIR/plugins" ]]; then
        export VLC_PLUGIN_PATH="$VLCDIR/plugins"
    fi
fi

exec "$APPDIR/Doremi" "$@"
