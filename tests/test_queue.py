from doremi.audio.queue import PlayQueue, QueueItem, RepeatMode


def _item(video_id: str, duration_ms: int = 200000) -> QueueItem:
    return QueueItem(
        video_id=video_id,
        title=f"Title {video_id}",
        artist="Artist",
        album="Album",
        duration_ms=duration_ms,
        thumbnail_url="",
    )


def _queue(n: int = 3) -> PlayQueue:
    q = PlayQueue()
    q.set_queue([_item(f"v{i}") for i in range(n)], start_index=0)
    return q


def test_current_returns_none_when_empty():
    q = PlayQueue()
    assert q.current is None
    assert q.current_index == -1


def test_set_queue_sets_index():
    q = _queue(3)
    assert q.current_index == 0
    assert q.current.video_id == "v0"


def test_advance_moves_to_next():
    q = _queue(3)
    item = q.advance()
    assert q.current_index == 1
    assert item.video_id == "v1"


def test_advance_past_end_returns_none_when_repeat_off():
    q = _queue(3)
    q.advance()
    q.advance()
    assert q.current_index == 2
    assert q.advance() is None
    # index stays at last
    assert q.current_index == 2


def test_advance_repeat_all_wraps_to_zero():
    q = _queue(3)
    q.repeat_mode = RepeatMode.ALL
    q.advance()
    q.advance()
    item = q.advance()
    assert q.current_index == 0
    assert item.video_id == "v0"


def test_advance_repeat_one_keeps_same_index_and_item():
    q = _queue(3)
    q.repeat_mode = RepeatMode.ONE
    first = q.current
    item = q.advance()
    assert q.current_index == 0
    assert item is first
    assert item.video_id == "v0"


def test_next_item_repeat_one_returns_current():
    q = _queue(3)
    q.repeat_mode = RepeatMode.ONE
    assert q.next_item.video_id == "v0"


def test_next_item_repeat_all_wraps():
    q = _queue(3)
    q.repeat_mode = RepeatMode.ALL
    q.advance()
    q.advance()
    assert q.next_item.video_id == "v0"


def test_next_item_repeat_off_returns_none_past_end():
    q = _queue(3)
    q.advance()
    q.advance()
    assert q.next_item is None


def test_add_next_inserts_after_current():
    q = _queue(3)
    q.advance()  # index 1
    q.add_next(_item("vx"))
    assert q.items[2].video_id == "vx"
    assert q.current_index == 1


def test_add_to_end_appends():
    q = _queue(3)
    q.add_to_end(_item("vx"))
    assert q.items[-1].video_id == "vx"


def test_remove_at_adjusts_index():
    q = _queue(3)
    q.advance()  # index 1
    q.remove_at(0)
    assert q.current_index == 0
    assert q.current.video_id == "v1"


def test_go_back_decrements_index():
    q = _queue(3)
    q.advance()
    q.advance()
    item = q.go_back()
    assert q.current_index == 1
    assert item.video_id == "v1"


def test_jump_to_sets_index():
    q = _queue(3)
    item = q.jump_to(2)
    assert q.current_index == 2
    assert item.video_id == "v2"


def test_toggle_repeat_cycles_off_all_one():
    q = _queue(2)
    assert q.repeat_mode == RepeatMode.OFF
    assert q.toggle_repeat() == RepeatMode.ALL
    assert q.toggle_repeat() == RepeatMode.ONE
    assert q.toggle_repeat() == RepeatMode.OFF


def test_toggle_shuffle_enables_and_restores_original():
    q = _queue(3)
    q.toggle_shuffle()
    assert q.shuffle_enabled is True
    # current stays first in shuffled queue
    assert q.current_index == 0
    q.toggle_shuffle()
    assert q.shuffle_enabled is False
    # original order restored
    assert [i.video_id for i in q.items] == ["v0", "v1", "v2"]


def test_move_item_reorders_and_keeps_current():
    q = _queue(3)
    q.move_item(0, 2)
    assert [i.video_id for i in q.items] == ["v1", "v2", "v0"]


def test_to_dict_from_dict_roundtrip():
    q = _queue(3)
    q.repeat_mode = RepeatMode.ALL
    q.advance()
    data = q.to_dict()
    restored = PlayQueue.from_dict(data)
    assert restored.current_index == q.current_index
    assert restored.repeat_mode == RepeatMode.ALL
    assert [i.video_id for i in restored.items] == ["v0", "v1", "v2"]
    # stream_url stripped during serialization
    assert all(i.stream_url is None for i in restored.items)


def test_from_dict_handles_unknown_video_id_gracefully():
    restored = PlayQueue.from_dict({"items": [{"video_id": "v1"}]})
    # QueueItem requires all fields; missing fields should fall back to empty
    assert restored.current is None or restored.current.video_id == "v1"


def test_removed_item_does_not_return_after_shuffle_roundtrip():
    q = _queue(3)
    q.remove_at(1)
    q.toggle_shuffle()
    q.toggle_shuffle()
    assert [item.video_id for item in q.items] == ["v0", "v2"]


def test_move_preserves_current_occurrence_of_duplicate_song():
    first, second, other = _item("same"), _item("same"), _item("other")
    q = PlayQueue()
    q.set_queue([first, second, other], 1)
    q.move_item(2, 0)
    assert q.current is second


def test_shuffle_restores_current_occurrence_of_duplicate_song():
    first, second = _item("same"), _item("same")
    q = PlayQueue()
    q.set_queue([first, second], 1)
    q.toggle_shuffle()
    q.toggle_shuffle()
    assert q.current is second


def test_empty_queue_can_be_set_while_shuffle_enabled():
    q = _queue()
    q.toggle_shuffle()
    q.set_queue([])
    assert q.current is None
    assert q.current_index == -1


def test_restored_shuffle_can_remove_track_without_resurrecting_it():
    q = _queue(3)
    q.toggle_shuffle()
    restored = PlayQueue.from_dict(q.to_dict())
    removed = restored.items[1].video_id
    current = restored.current
    restored.remove_at(1)
    restored.toggle_shuffle()
    assert removed not in [item.video_id for item in restored.items]
    assert restored.current is current


def test_add_next_in_shuffle_is_next_in_original_order_too():
    q = _queue(3)
    q.jump_to(2)
    q.toggle_shuffle()
    q.add_next(_item("new"))
    q.toggle_shuffle()
    assert q.current.video_id == "v2"
    assert q.next_item.video_id == "new"
