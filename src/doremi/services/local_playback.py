"""Filesystem availability at playback boundaries; never modifies media."""
import os
from pathlib import Path


def available_local_path(path) -> str | None:
    """A download flag alone is not evidence of a readable, nonempty file."""
    if not isinstance(path, (str, Path)) or not path:
        return None
    try:
        candidate = Path(path)
        if candidate.is_file() and candidate.stat().st_size > 0 and os.access(candidate, os.R_OK):
            return str(candidate)
    except (OSError, ValueError):
        pass
    return None
