from __future__ import annotations

import json
import logging
from pathlib import Path

from doremi.config.paths import AppDirs

logger = logging.getLogger(__name__)


class SearchHistory:
    """Persistent, UI-independent recent-search store."""

    def __init__(self, path: Path | None = None, limit: int = 20) -> None:
        self._path = path or AppDirs.data / "search_history.json"
        self._limit = limit

    def load(self) -> list[str]:
        try:
            if not self._path.exists():
                return []
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return []
            return self._normalize(raw)
        except Exception as exc:
            logger.debug("Could not load search history: %s", exc)
            return []

    def commit(self, history: list[str], query: str) -> list[str]:
        cleaned = query.strip()
        if not cleaned:
            return self._normalize(history)
        updated = [cleaned, *(item for item in history if item.casefold() != cleaned.casefold())]
        updated = self._normalize(updated)
        self.save(updated)
        return updated

    def remove(self, history: list[str], query: str) -> list[str]:
        updated = [item for item in history if item != query]
        updated = self._normalize(updated)
        self.save(updated)
        return updated

    def save(self, history: list[str]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._normalize(history), ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.debug("Could not save search history: %s", exc)

    def _normalize(self, values: list[object]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str):
                continue
            cleaned = value.strip()
            key = cleaned.casefold()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
            if len(result) == self._limit:
                break
        return result
