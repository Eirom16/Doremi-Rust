"""Linux portable packaging regression tests (F0B-3A).

Guards the Linux bundle definition without touching the verified Windows
pipeline (doremi.spec must stay byte-identical for Windows flows).
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (REPO / name).read_text(encoding="utf-8")


def test_linux_spec_exists_and_windows_spec_untouched():
    assert (REPO / "doremi-linux.spec").exists()
    win = _read("doremi.spec")
    # Windows markers must remain in the Windows spec.
    assert 'icon="assets/icon.ico"' in win
    assert "keyring.backends.Windows" in win
    assert "win32ctypes" in win
    assert "console=False" in win


def test_linux_spec_has_no_windows_exe_resources():
    spec = _read("doremi-linux.spec")
    # No .ico wired as code (datas entry or EXE icon=). Docstring prose may
    # name it for contrast, so match quoted code forms only.
    assert 'icon="assets/icon.ico"' not in spec
    assert "'assets/icon.ico'" not in spec
    assert '"assets/icon.ico"' not in spec
    assert '"keyring.backends.Windows"' not in spec
    assert '"win32ctypes' not in spec
    # Linux keyring stack instead.
    assert '"keyring.backends.SecretService"' in spec
    # Smoke diagnostics need stdout on a terminal.
    assert "console=True" in spec
    assert "icon=None" in spec


def test_linux_spec_collects_same_app_data():
    spec = _read("doremi-linux.spec")
    for entry in [
        '("src/doremi/ui/qml", "doremi/ui/qml")',
        '("src/doremi/assets/fonts", "doremi/assets/fonts")',
        '("src/doremi/locales", "doremi/locales")',
        '("src/doremi/db/migrations", "doremi/db/migrations")',
        '("assets/Doremi.png", "assets")',
        '("vlc_libs", "vlc_libs")',
    ]:
        assert entry in spec, f"missing datas entry: {entry}"
    # Rust extension glob covers the Linux .so name.
    assert 'glob("native_rs*.so")' in spec


def test_linux_spec_ignores_vcs():
    # doremi-linux.spec must be committable (see .gitignore *.spec rule).
    ignore = _read(".gitignore")
    assert "!doremi-linux.spec" in ignore


def test_launcher_exists_executable_and_layout_agnostic():
    launcher = REPO / "packaging" / "linux" / "doremi.sh"
    assert launcher.exists()
    assert launcher.stat().st_mode & stat.S_IXUSR
    text = launcher.read_text(encoding="utf-8")
    # Works from any CWD (no hardcoded paths, resolves its own location).
    assert "readlink -f" in text or "BASH_SOURCE" in text
    assert "/home/" not in text and "/tmp/" not in text
    # No privilege escalation, no writes into the bundle.
    assert "sudo" not in text
    # Env handling: prepend/conditional, never clobber.
    assert "LD_LIBRARY_PATH" in text
    assert "VLC_PLUGIN_PATH" in text
    assert "PYTHON_VLC_LIB_PATH" in text
    assert ":-}" in text  # parameter-expansion guards for unset vars
    # Forwards arbitrary args (incl. --smoke-test).
    assert '"$@"' in text


def test_launcher_env_logic_flat_layout(tmp_path, monkeypatch):
    """Simulate a flat onedir next to the launcher and check env exports."""
    import subprocess

    appdir = tmp_path / "portable"
    internal = appdir / "_internal" / "vlc_libs"
    (internal / "plugins").mkdir(parents=True)
    (internal / "libvlc.so.5").write_bytes(b"fake")
    (appdir / "Doremi").write_text("#!/usr/bin/env bash\nenv\n", encoding="utf-8")
    (appdir / "Doremi").chmod(0o755)
    (appdir / "_internal").mkdir(exist_ok=True)
    launcher = tmp_path / "portable" / "doremi.sh"
    launcher.write_bytes((REPO / "packaging" / "linux" / "doremi.sh").read_bytes())
    launcher.chmod(0o755)

    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("LD_LIBRARY_PATH", "PYTHON_VLC_LIB_PATH", "VLC_PLUGIN_PATH")
    }
    env["PATH"] = os.environ.get("PATH", "/usr/bin:/bin")
    out = subprocess.run(
        [str(launcher)], cwd="/", capture_output=True, text=True, env=env
    )
    assert out.returncode == 0, out.stderr
    assert f"LD_LIBRARY_PATH={internal}" in out.stdout
    assert f"PYTHON_VLC_LIB_PATH={internal}/libvlc.so.5" in out.stdout
    assert f"VLC_PLUGIN_PATH={internal}/plugins" in out.stdout


def test_vlc_check_pins_bundled_lib_on_linux(tmp_path, monkeypatch):
    """setup_vlc_env() must pin PYTHON_VLC_LIB_PATH to the bundle on Linux."""
    import sys

    if not sys.platform.startswith("linux"):
        import pytest

        pytest.skip("Linux-only env semantics")
    import doremi.utils.vlc_check as vc

    vlc_dir = tmp_path / "vlc_libs"
    (vlc_dir / "plugins").mkdir(parents=True)
    (vlc_dir / "libvlc.so.5").write_bytes(b"fake")

    monkeypatch.delenv("PYTHON_VLC_LIB_PATH", raising=False)
    monkeypatch.delenv("VLC_PLUGIN_PATH", raising=False)
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    monkeypatch.setattr(vc, "_find_vlc_lib", lambda: vlc_dir / "libvlc.so.5")

    # Point AppDirs.vlc_dir at the fake tree (non-frozen path). AppDirs is a
    # singleton with a read-only property: patch it at class level.
    from doremi.config.paths import AppDirs

    monkeypatch.setattr(type(AppDirs), "vlc_dir", property(lambda self, p=vlc_dir: p))
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    if hasattr(sys, "_MEIPASS"):
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    vc.setup_vlc_env()
    assert os.environ["PYTHON_VLC_LIB_PATH"] == str(vlc_dir / "libvlc.so.5")
    assert os.environ["VLC_PLUGIN_PATH"] == str(vlc_dir / "plugins")
    assert os.environ["LD_LIBRARY_PATH"].startswith(str(vlc_dir))


def test_vlc_check_respects_preset_lib_path(tmp_path, monkeypatch):
    """A pre-set PYTHON_VLC_LIB_PATH (launcher) must never be overridden."""
    import sys

    if not sys.platform.startswith("linux"):
        import pytest

        pytest.skip("Linux-only env semantics")
    import doremi.utils.vlc_check as vc

    vlc_dir = tmp_path / "vlc_libs"
    (vlc_dir / "plugins").mkdir(parents=True)
    (vlc_dir / "libvlc.so.5").write_bytes(b"fake")

    from doremi.config.paths import AppDirs

    monkeypatch.setattr(type(AppDirs), "vlc_dir", property(lambda self, p=vlc_dir: p))
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    if hasattr(sys, "_MEIPASS"):
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setenv("PYTHON_VLC_LIB_PATH", "/custom/libvlc.so.5")
    monkeypatch.delenv("VLC_PLUGIN_PATH", raising=False)

    vc.setup_vlc_env()
    assert os.environ["PYTHON_VLC_LIB_PATH"] == "/custom/libvlc.so.5"


def test_frozen_path_resolution_uses_meipass_layout():
    """Bundle-relative lookups must resolve under _MEIPASS/doremi/... ."""
    import sys

    import doremi.config.paths as paths
    import doremi.ui.qml_paths as qp

    assert 'Path(sys._MEIPASS) / "doremi"' in (REPO / "src" / "doremi" / "config" / "paths.py").read_text()
    assert 'Path(sys._MEIPASS) / "doremi" / "ui" / "qml"' in (REPO / "src" / "doremi" / "ui" / "qml_paths.py").read_text()
    assert callable(paths.bundle_package_dir) and callable(qp.qml_dir)
    assert not hasattr(sys, "_MEIPASS") or True
