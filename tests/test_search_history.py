from doremi.services.search_history import SearchHistory


def test_history_normalizes_persists_and_deduplicates_case_insensitively(tmp_path):
    store = SearchHistory(tmp_path / "history.json", limit=3)

    history = store.commit([], "  Jazz  ")
    history = store.commit(history, "rock")
    history = store.commit(history, "JAZZ")
    history = store.commit(history, "ambient")
    history = store.commit(history, "classical")

    assert history == ["classical", "ambient", "JAZZ"]
    assert store.load() == history


def test_history_ignores_invalid_saved_values_and_removes_entries(tmp_path):
    path = tmp_path / "history.json"
    path.write_text('["Jazz", " jazz ", 4, "", "Rock"]', encoding="utf-8")
    store = SearchHistory(path)

    assert store.load() == ["Jazz", "Rock"]
    assert store.remove(store.load(), "Jazz") == ["Rock"]
