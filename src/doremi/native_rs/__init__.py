# Doremi native Rust acceleration module.
#
# Loads the compiled extension (built with maturin). Resolution order:
#   1. `native_rs` installed top-level (maturin develop / pip wheel).
#   2. Extension file next to this __init__.py (in-tree build, PyInstaller
#      bundle where src/doremi is bundled as data).
# If no extension is found, raises ImportError — Python callers have their
# own fallback logic.

from __future__ import annotations


def _load_native():
    try:
        import native_rs as ext

        return ext
    except ImportError:
        pass

    import importlib.util
    import sys
    from pathlib import Path

    here = Path(__file__).resolve().parent
    candidates = sorted(here.glob("native_rs*.so")) + sorted(here.glob("native_rs*.pyd"))
    for path in candidates:
        try:
            spec = importlib.util.spec_from_file_location("native_rs", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules["native_rs"] = module
            spec.loader.exec_module(module)
            return module
        except (ImportError, OSError):
            sys.modules.pop("native_rs", None)
    return None


_ext = _load_native()
if _ext is None:
    raise ImportError("native_rs extension module not found")

__all__ = [name for name in dir(_ext) if not name.startswith("_")]
globals().update({name: getattr(_ext, name) for name in __all__})

_NATIVE_AVAILABLE = True
