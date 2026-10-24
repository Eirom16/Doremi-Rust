"""Collection namespaces at command boundaries, independent of Qt/network."""
import re

LOCAL_PLAYLIST_PREFIXES = ("session:", "smart:", "local-list:", "local_")


def session_identity(identity):
    """Parse a valid UI session without constructing a service or querying DB."""
    if not isinstance(identity, str) or not re.fullmatch(r"session:[1-9][0-9]*:[1-9][0-9]*(?::[0-9]+)?", identity):
        return None
    from doremi.services.listening_periods import ListeningPeriods
    try:
        first, last, cutoff = ListeningPeriods.parse_identity(identity)
        return (first, last, cutoff) if first <= last else None
    except (ValueError, OverflowError, OSError):
        return None


def has_local_playlist_namespace(identity) -> bool:
    """Reserved namespace, including malformed identities; not route validity."""
    return isinstance(identity, str) and identity.startswith(LOCAL_PLAYLIST_PREFIXES)


def is_downloadable_playlist_identity(identity) -> bool:
    """Only opaque provider IDs; never URLs, routes or local namespaces.

    YouTubeMusicClient strips one VL browse prefix. Check the effective ID
    too, without changing the original ID passed to existing remote callers.
    """
    if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", identity):
        return False
    effective = identity[2:] if identity.startswith("VL") else identity
    return bool(effective) and not has_local_playlist_namespace(effective)
