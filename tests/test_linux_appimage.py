"""Linux AppImage packaging regression tests (F0B-3B).

Guards the AppDir definition built on top of the verified F0B-3A portable
(PyInstaller onedir + doremi.sh launcher). Does NOT touch the verified
Windows pipeline (doremi.spec must stay byte-identical).
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APPIMG = REPO / "packaging" / "appimage"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_appimage_sources_exist_and_executable():
    apprun = APPIMG / "AppRun"
    builder = APPIMG / "build-appdir.sh"
    desktop = APPIMG / "doremi.desktop"
    addendum = APPIMG / "APPIMAGE-NOTICES.txt"
    assert apprun.exists() and desktop.exists() and builder.exists() and addendum.exists()
    assert apprun.stat().st_mode & stat.S_IXUSR, "AppRun must be executable"
    assert builder.stat().st_mode & stat.S_IXUSR, "build-appdir.sh must be executable"
    # Icon source referenced by the desktop file must exist.
    assert (REPO / "assets" / "Doremi.png").exists()
    # Licenses from the portable must be reused, plus the runtime addendum.
    assert (REPO / "LICENSE").exists()
    assert (REPO / "packaging" / "linux" / "THIRD-PARTY-NOTICES.txt").exists()
    add_text = _read(addendum)
    assert "type-2 runtime" in add_text or "type2-runtime" in add_text
    assert "BLOCKED" in add_text


def test_apprun_invokes_verified_launcher():
    text = _read(APPIMG / "AppRun")
    # Single source of truth: AppRun delegates to usr/bin/doremi (the
    # verified doremi.sh copy). No duplicated VLC env logic here.
    assert "usr/bin/doremi" in text
    assert '"$@"' in text, "AppRun must forward arbitrary args"
    code = "\n".join(
        ln for ln in text.splitlines()
        if not ln.lstrip().startswith("#")
    )
    assert "PYTHON_VLC_LIB_PATH=" not in code, "VLC env belongs in the launcher, not AppRun"
    assert "VLC_PLUGIN_PATH=" not in code
    assert "LD_LIBRARY_PATH=" not in code
    # APPDIR fallback for direct squashfs-root/AppRun execution.
    assert 'APPDIR:-' in text or "APPDIR:-" in text
    assert "readlink -f" in text
    # Must not change directory (caller's CWD preserved for smoke cwd check).
    assert "cd " not in text.replace("readlink", "").replace("# ", ""), \
        "AppRun must not cd away from the caller's CWD"


def test_build_appdir_preserves_bundle_intact():
    text = _read(APPIMG / "build-appdir.sh")
    # Intact copy with permissions.
    assert "cp -a" in text
    assert "usr/bin/Doremi" in text
    assert "usr/bin/_internal" in text
    assert "usr/bin/doremi" in text
    assert ".DirIcon" in text
    # Deliberately no second copy of Qt/VLC via deploy tools (code, not comments).
    code = "\n".join(
        ln for ln in text.splitlines()
        if not ln.lstrip().startswith("#")
    ).lower()
    assert "linuxdeploy " not in code and "linuxdeploy\t" not in code
    assert "linuxdeployqt" not in code
    assert "\nlinuxdeploy" not in code
    # No host-incompatible libs, no stripping to save megabytes (code only).
    assert "strip --" not in code and "eu-strip" not in code
    # Required bundle entries are asserted by the builder itself.
    for marker in [
        "doremi/ui/qml/MainShell.qml",
        "vlc_libs/libvlc.so.5",
        "native_rs",
        "libqxcb.so",
        "libqoffscreen.so",
        "usr/share/doc/doremi/LICENSE.txt",
        "THIRD-PARTY-NOTICES.txt",
        "APPIMAGE-NOTICES.txt",
    ]:
        assert marker in text, f"builder must check {marker}"


def test_appimage_desktop_fields():
    lines = _read(APPIMG / "doremi.desktop").splitlines()
    kv = {}
    for ln in lines:
        if "=" in ln and not ln.startswith("[") and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            kv[k.strip()] = v.strip()
    assert lines[0].strip() == "[Desktop Entry]"
    assert kv.get("Name") == "Doremi"
    assert kv.get("Type") == "Application"
    assert kv.get("Terminal") == "false"
    # Exec without absolute path (AppImage spec); %U placeholder allowed.
    assert kv.get("Exec", "").split()[0] == "doremi"
    # Icon without path/extension; the file + .DirIcon are created by the builder.
    assert kv.get("Icon") == "doremi"
    assert "Audio" in kv.get("Categories", "")
    # Protocol associations are NOT advertised: no handler is proven.
    assert "MimeType" not in kv, \
        "AppImage desktop must not claim x-scheme-handler/doremi (unproven)"
    # Original portable desktop stays untouched (still advertises MimeType;
    # that claim remains out of scope / unverified).
    orig = _read(REPO / "packaging" / "doremi.desktop")
    assert "MimeType=x-scheme-handler/doremi;" in orig


def test_desktop_file_validates():
    import shutil

    if shutil.which("desktop-file-validate") is None:
        import pytest

        pytest.skip("desktop-file-validate not installed")
    out = subprocess.run(
        ["desktop-file-validate", str(APPIMG / "doremi.desktop")],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stdout + out.stderr


def test_apprun_end_to_end_with_fake_bundle(tmp_path):
    """Fake AppDir + AppRun must export the bundled VLC env and exec."""
    appdir = tmp_path / "Doremi.AppDir"
    bindir = appdir / "usr" / "bin"
    internal = bindir / "_internal" / "vlc_libs"
    (internal / "plugins").mkdir(parents=True)
    (internal / "libvlc.so.5").write_bytes(b"fake")
    # Stub binary: dumps env (like the launcher test in F0B-3A).
    exe = bindir / "Doremi"
    exe.write_text("#!/usr/bin/env bash\nenv\n", encoding="utf-8")
    exe.chmod(0o755)
    (bindir / "_internal").mkdir(exist_ok=True)
    # Real launcher + real AppRun copies.
    launcher = bindir / "doremi"
    launcher.write_bytes((REPO / "packaging" / "linux" / "doremi.sh").read_bytes())
    launcher.chmod(0o755)
    apprun = appdir / "AppRun"
    apprun.write_bytes((APPIMG / "AppRun").read_bytes())
    apprun.chmod(0o755)

    env = {k: v for k, v in os.environ.items()
           if k not in ("APPDIR", "LD_LIBRARY_PATH", "PYTHON_VLC_LIB_PATH", "VLC_PLUGIN_PATH")}
    env["PATH"] = os.environ.get("PATH", "/usr/bin:/bin")
    out = subprocess.run([str(apprun)], cwd="/", capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert f"LD_LIBRARY_PATH={internal}" in out.stdout
    assert f"PYTHON_VLC_LIB_PATH={internal}/libvlc.so.5" in out.stdout
    assert f"VLC_PLUGIN_PATH={internal}/plugins" in out.stdout


def test_apprun_forwards_args(tmp_path):
    """AppRun must forward args (e.g. --smoke-test) to the binary."""
    appdir = tmp_path / "Doremi.AppDir"
    bindir = appdir / "usr" / "bin"
    bindir.mkdir(parents=True)
    (bindir / "_internal").mkdir(exist_ok=True)
    exe = bindir / "Doremi"
    exe.write_text('#!/usr/bin/env bash\necho "ARGS:$*"\n', encoding="utf-8")
    exe.chmod(0o755)
    launcher = bindir / "doremi"
    launcher.write_bytes((REPO / "packaging" / "linux" / "doremi.sh").read_bytes())
    launcher.chmod(0o755)
    apprun = appdir / "AppRun"
    apprun.write_bytes((APPIMG / "AppRun").read_bytes())
    apprun.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = os.environ.get("PATH", "/usr/bin:/bin")
    out = subprocess.run([str(apprun), "--smoke-test"], capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert "ARGS:--smoke-test" in out.stdout
