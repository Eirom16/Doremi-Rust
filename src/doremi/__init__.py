def _resolve_version() -> str:
    # Frozen builds (PyInstaller) stamp src/doremi/_build_version.py at build
    # time: no .git metadata and no importable dist-info exist in the bundle,
    # so neither fallback below would yield the real build version.
    try:
        from doremi._build_version import BUILD_VERSION as _stamped
        if _stamped:
            return _stamped
    except Exception:
        pass

    try:
        import subprocess
        from pathlib import Path

        out = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            cwd=str(Path(__file__).resolve().parent),
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip().lstrip("v")
    except Exception:
        pass

    try:
        from importlib.metadata import version as _dist_version
        return _dist_version("doremi")
    except Exception:
        pass

    return "2.1.4"


__version__ = _resolve_version()
