"""Explainable Home composition, independent of Qt and remote services."""
from copy import deepcopy
from urllib.parse import urlencode, parse_qs, urlsplit

from doremi.db.experience_repository import ExperienceRepository, SMART_TITLES


def identity(item):
    if item.get("videoId"):
        return "track:" + str(item["videoId"])
    route = item.get("navigate", "")
    if route.startswith("play:"):
        return "track:" + route[5:]
    parsed = urlsplit(route)
    params = {k: v[-1] for k, v in parse_qs(parsed.query).items() if k not in {"resume", "position", "next", "autoplay"}}
    return parsed.path + ("?" + urlencode(sorted(params.items())) if params else "")


def diverse_tracks(items, limit=6):
    selected, deferred, counts, seen = [], [], {}, set()
    for item in items:
        key = identity(item)
        if not key or key in seen:
            continue
        seen.add(key)
        artist = str(item.get("artist", "")).strip().casefold()
        if artist and counts.get(artist, 0) >= 2:
            deferred.append(item)
        else:
            selected.append(item)
            counts[artist] = counts.get(artist, 0) + 1
        if len(selected) == limit:
            break
    return selected + deferred[:max(0, limit - len(selected))]


def compose_home(remote, personal_sections, tracks):
    data = deepcopy(remote)
    seen = set()

    def unique(items, limit):
        result = []
        for item in items:
            key = identity(item)
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item)
            if len(result) == limit:
                break
        return result

    data["personal"] = []
    for section in personal_sections:
        items = unique(section["items"], 6)
        if items:
            data["personal"].append(dict(title=section["title"], items=items))
    data["tiles"] = unique(diverse_tracks(tracks + data.get("tiles", [])), 6)
    if data.get("_source") in {"cache", "empty", "offline"}:
        # The cache synthesizes a spotlight from its songs. Prefer keeping the
        # playable song list when only one cached song is available.
        data["songs"] = unique(data.get("songs", []), 16)
        data["spotlight"] = unique(data.get("spotlight", []), 1)
        data["horizontal"] = unique(data.get("horizontal", []), 45)
    else:
        data["spotlight"] = unique(data.get("spotlight", []), 1)
        data["horizontal"] = unique(data.get("horizontal", []), 45)
        data["songs"] = unique(data.get("songs", []), 16)
    sections = {}
    for item in data["horizontal"]:
        sections.setdefault(item.get("section_title", ""), []).append(item)
    data["sections"] = [dict(title=title, items=items) for title, items in sections.items() if title]
    return data


async def personalized_home(remote):
    repo = ExperienceRepository()
    offline = remote.get("offline", False) or remote.get("_source") == "offline"
    continuing = await repo.continue_listening(offline_only=offline)
    for card in continuing:
        card["navigate"] += "&" + urlencode({"resume": card["video_id"], "position": card["position_ms"], "next": int(card["completed"])})
    quick = await repo.quick_access()
    if offline:
        quick = [card for card in quick if parse_qs(urlsplit(card["navigate"]).query).get("id", [""])[-1].startswith(("local-list:", "local_"))]
    from doremi.services.listening_periods import ListeningPeriods
    periods = await ListeningPeriods().recent(limit=3)
    # Only six bounded collection queries, irrespective of history length.
    collections = []
    frequent = []
    for rule, title in SMART_TITLES.items():
        tracks = await repo.smart_tracks(rule, limit=6, offline_only=offline)
        if tracks:
            collections.append(dict(title=title, subtitle=f"{len(tracks)}+ canciones" if len(tracks) == 6 else f"{len(tracks)} canciones",
                                    thumbnail_url=tracks[0]["thumbnail_url"], navigate=f"playlist?id=smart:{rule}"))
        if rule == "repeat":
            frequent = tracks
    data = compose_home(remote, [dict(title="Continuar escuchando", items=continuing),
                                 dict(title="Acceso rápido", items=quick),
                                 dict(title="Sesiones musicales", items=periods),
                                 dict(title="Hechas con tu música", items=collections)], frequent)
    from doremi.db.repository import DownloadRepository
    visible_tracks = data["tiles"] + data["songs"]
    available = await DownloadRepository().get_available_video_ids([t.get("videoId", "") for t in visible_tracks])
    for track in visible_tracks:
        track["is_downloaded"] = bool(track.get("is_downloaded") or track.get("videoId") in available)
    return data
