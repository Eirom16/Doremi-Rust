"""Keep individual artist identities when displaying track credits."""
from __future__ import annotations

import re

_SEPARATOR = re.compile(r"\s*(?:[,;]|\s+(?:feat\.?|ft\.?|featuring)\s+)\s*", re.I)
_UNKNOWN = {"unknown", "unknown artist", "artista desconocido", "desconocido"}


def artist_credits(artists=None, fallback: str = "") -> list[dict[str, str]]:
    """Prefer structured credits; split only legacy, flattened artist strings.

    Never split ampersands: they can be part of a band's name. Structured
    names, including names containing commas, remain intact.
    """
    if isinstance(artists, dict):
        artists = [artists]
    if not isinstance(artists, (list, tuple)) or not artists:
        text = artists if isinstance(artists, str) and artists.strip() else fallback
        artists = _SEPARATOR.split(str(text or ""))
    credits = []
    seen = set()
    for entry in artists:
        if isinstance(entry, dict):
            name = str(entry.get("name") or entry.get("artist") or "").strip()
            identity = str(entry.get("id") or entry.get("browseId") or entry.get("channelId") or "")
        elif isinstance(entry, str):
            name, identity = entry.strip(), ""
        else:
            continue
        key = (name.casefold(), identity)
        if name and name.casefold() not in _UNKNOWN and key not in seen:
            credits.append({"name": name, "id": identity})
            seen.add(key)
    return credits
