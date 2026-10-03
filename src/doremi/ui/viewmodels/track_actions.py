"""One action contract for track viewmodels; persistence stays in controllers."""


def dispatch_track_action(vm, item, action):
    if not item or not item.get("videoId"):
        return False
    video_id = item["videoId"]
    title, artist = item.get("title", ""), item.get("artist", "")
    thumbnail = item.get("thumbnail_url", "")
    local = video_id.startswith("local:") or video_id == "local"
    mapping = {
        "play_next": ("play_next_requested", (video_id, title, artist, thumbnail)),
        "add_to_queue": ("add_to_queue_requested", (video_id, title, artist, thumbnail)),
        "like": ("like_requested", (video_id, None)),
        "add_to_playlist": ("add_to_playlist_requested", (video_id, title)),
        "download": ("download_requested", (video_id, title, artist, thumbnail)),
        "delete_download": ("delete_download_requested", (video_id,)),
        "go_artist": ("artist_clicked", (artist,)),
        "go_album": ("album_clicked", (item.get("album", ""),)),
        "copy_link": ("copy_link_requested", (video_id,)),
    }
    if action not in mapping:
        return False
    # Imported audio has no remote identifier, even if it has artist tags.
    if local and action in {"download", "delete_download", "go_artist", "go_album", "copy_link"}:
        return True
    signal_name, arguments = mapping[action]
    if action in {"go_artist", "go_album"} and not arguments[0]:
        return True
    signal = getattr(vm, signal_name, None)
    if signal is not None:
        signal.emit(*arguments)
    return True


def dispatch_collection_action(vm, tracks, action):
    if action == "play":
        vm.play_all()
    elif action == "shuffle":
        vm.play_shuffle()
    elif action in {"play_next", "add_to_queue"}:
        # Repeated add-next inserts immediately after current; reverse emission
        # keeps the collection's order. Queue controllers capture its origin.
        for track in reversed(tracks) if action == "play_next" else tracks:
            dispatch_track_action(vm, track, action)
