"""Capture origin at the user-action boundary, before asynchronous work."""
from urllib.parse import parse_qs, urlsplit

CONTEXT_TYPES = frozenset({
    "playlist", "album", "artist", "search", "home", "library", "history",
    "downloads", "queue", "autoplay", "local", "unknown", "smart",
})


def playback_context(window) -> dict:
    path = getattr(window, "_current_path", "")
    if not isinstance(path, str):
        path = ""
    parsed = urlsplit(path)
    kind = parsed.path
    params = parse_qs(parsed.query)
    identity = params.get("id", [""])[-1]
    if kind == "podcast":
        kind = "album"
    if kind == "now_playing":
        kind = "queue"
    if kind not in CONTEXT_TYPES:
        kind = "unknown"
    screen = getattr(window, f"{kind}_screen", None)
    vm = getattr(screen, "_vm", None)
    title = getattr(vm, "title", "") or getattr(vm, "artistName", "")
    if not isinstance(title, str):
        title = ""
    if kind == "search":
        identity = params.get("query", [""])[-1]
        title = identity
    if kind == "library" and getattr(vm, "tab", "") == "local":
        kind = "local"
    if kind == "playlist" and identity.startswith("smart:"):
        kind = "smart"
    return dict(context_type=kind, context_id=identity, context_title=title)
