# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller bundle for Doremi (Linux x86_64 portable, onedir).

Build on Ubuntu 22.04 x86_64 with Python 3.12::

    sudo apt-get install -y vlc libvlc-dev
    pip install . pyinstaller maturin
    mkdir -p vlc_libs/plugins
    cp /usr/lib/x86_64-linux-gnu/libvlc.so.5* \
       /usr/lib/x86_64-linux-gnu/libvlccore.so* vlc_libs/
    cp -r /usr/lib/x86_64-linux-gnu/vlc/plugins/* vlc_libs/plugins/
    (cd src/doremi/native_rs && maturin build --release --locked --out dist)
    pip install src/doremi/native_rs/dist/*.whl
    python - <<'EOF' > src/doremi/_build_version.py   # stamp, see linux-portable.yml
    print('BUILD_VERSION = "2.1.4"')
    print('BUILD_ID = "local"')
    EOF
    pyinstaller doremi-linux.spec

Layout notes (must match the frozen branches in src):
- QML/fonts/locales/migrations are collected under ``doremi/...`` at the
  bundle root (``sys._MEIPASS``); see ``ui/qml_paths.py`` and
  ``config/paths.py::bundle_package_dir``.
- Root icons go to ``assets/`` (``AppDirs.root`` when frozen).
- ``vlc_libs/`` (libvlc.so.5 + libvlccore + plugins tree, prepared from the
  Ubuntu 22.04 libvlc install) is collected as data;
  ``utils/vlc_check.py`` discovers it via ``_MEIPASS`` and pins it through
  ``PYTHON_VLC_LIB_PATH``/``LD_LIBRARY_PATH``/``VLC_PLUGIN_PATH``. The
  ``packaging/linux/doremi.sh`` launcher pre-exports the same variables
  before exec so the loader never depends on a system VLC.
- The Rust wheel installs a ``native_rs`` package (shim + ``native_rs.abi3.so``).
  PyInstaller collects it automatically; the extension binary is additionally
  placed next to the ``doremi.native_rs`` bridge so its file-glob fallback
  also resolves inside the bundle.

Linux differences vs doremi.spec (Windows, verified F0B-2B — DO NOT merge):
- No ``icon=*.ico`` executable resource (PyInstaller only supports exe icons
  on Windows/macOS); runtime PNG icons are still shipped as data.
- ``console=True`` so ``--smoke-test`` diagnostics reach stdout on a terminal.
- keyring ``SecretService`` backend instead of ``Windows``/``win32ctypes``.
"""

import pathlib

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

APP_NAME = "Doremi"

datas = [
    ("src/doremi/ui/qml", "doremi/ui/qml"),
    ("src/doremi/assets/fonts", "doremi/assets/fonts"),
    ("src/doremi/locales", "doremi/locales"),
    # Alembic loads version scripts from disk by path at runtime, so the
    # migration SOURCES (not just the imported modules) must be present.
    ("src/doremi/db/migrations", "doremi/db/migrations"),
    ("assets/Doremi.png", "assets"),
    ("assets/Doremi_Withoth_Background.png", "assets"),
]
datas += collect_data_files("qt_material")
datas += collect_data_files("ytmusicapi")

binaries = []
try:
    import native_rs as _nrs

    _nrs_pkg = pathlib.Path(_nrs.__file__).parent
    for _p in sorted(_nrs_pkg.glob("native_rs*.pyd")) + sorted(_nrs_pkg.glob("native_rs*.so")):
        binaries.append((str(_p), "doremi/native_rs"))
except Exception as _e:  # pragma: no cover - build-env diagnostic only
    print(f"WARNING: native_rs wheel not importable at spec time ({_e}); "
          "relying on automatic collection")

_vlc_dir = pathlib.Path("vlc_libs")
if _vlc_dir.is_dir():
    datas.append(("vlc_libs", "vlc_libs"))
else:  # pragma: no cover - build-env diagnostic only
    print("WARNING: vlc_libs/ not found; bundle will fall back to system VLC")

hiddenimports = [
    # Generated at build time by CI; warning-only when absent (dev builds).
    "doremi._build_version",
    "vlc",
    "aiosqlite",
    "sqlalchemy.dialects.sqlite.aiosqlite",
    "alembic",
    "mako",
    "h2",
    "httpcore",
    "webbrowser",
    # stdlib modules only reached through attribute access (alembic/SQLAlchemy
    # logging setup); modulegraph cannot see them statically.
    "logging.config",
    "logging.handlers",
    # keyring backend discovery uses entry points; pin the Linux ones.
    # (Windows spec pins keyring.backends.Windows + win32ctypes instead.)
    "keyring.backends.SecretService",
    "keyring.backends.fail",
    "secretstorage",
    "dbus",
    "yt_dlp",
    "PIL",
]
hiddenimports += collect_submodules("yt_dlp.extractor")
hiddenimports += collect_submodules("yt_dlp.postprocessor")

# stdlib only; never app code. Anything else missing must fail loudly.
excludes = ["tkinter"]

a = Analysis(
    ["src/doremi/main.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)
