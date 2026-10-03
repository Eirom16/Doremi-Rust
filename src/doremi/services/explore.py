"""Provider category labels plus a small stable Doremi fallback."""
import unicodedata

STABLE_CATEGORIES = [
    ("Rock", "rock"), ("Pop", "pop"), ("Reggaetón", "reggaeton"),
    ("Salsa", "salsa"), ("Clásica", "classical"), ("Electrónica", "electronic"),
    ("Jazz", "jazz"), ("R&B", "r&b"), ("Reggae", "reggae"),
    ("Hip-Hop", "hip hop"), ("Anime", "anime soundtrack"),
    ("Gaming", "gaming soundtrack"), ("Workout", "workout"), ("Chill", "chill"),
]


def compose_categories(provider=None, limit=14):
    def key(title):
        return "".join(c for c in unicodedata.normalize("NFKD", title.casefold()) if c.isalnum())
    result, seen = [], set()
    candidates = [(c.get("title", ""), c.get("title", "")) for c in (provider or [])[:8] if isinstance(c, dict)]
    candidates += STABLE_CATEGORIES[-4:] + STABLE_CATEGORIES[:-4] if candidates else STABLE_CATEGORIES
    for title, query in candidates:
        if not isinstance(title, str) or not title.strip() or key(title) in seen:
            continue
        seen.add(key(title))
        result.append(dict(name=title.strip()[:100], query=query.strip()[:200]))
        if len(result) == limit:
            break
    return result


async def explore_categories(yt_client):
    from doremi.system.network import NetworkMonitor
    if NetworkMonitor.current_connectivity() is False:
        return []
    fetch = getattr(yt_client, "get_explore", None)
    if callable(fetch):
        try:
            data = await fetch()
            categories = data.get("moods_and_genres", []) if isinstance(data, dict) else []
            return compose_categories(categories)
        except Exception as exc:
            from loguru import logger
            logger.debug(f"Explore categories unavailable: {exc}")
    return compose_categories()
