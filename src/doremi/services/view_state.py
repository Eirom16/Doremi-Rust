"""Bounded in-session primitive state; no QML objects or persistent scrolls."""
from collections import OrderedDict
import math


class ViewStateStore:
    def __init__(self, limit=30):
        self.limit = limit
        self._states = OrderedDict()

    def save(self, route, state):
        if not isinstance(state, dict):
            return
        safe = {str(k)[:100]: v for k, v in state.items()
                if isinstance(v, (str, bool, int, float)) and not (isinstance(v, float) and not math.isfinite(v))}
        self._states[route] = {k: v[:500] if isinstance(v, str) else v for k, v in safe.items()}
        self._states.move_to_end(route)
        while len(self._states) > self.limit:
            self._states.popitem(last=False)

    def get(self, route):
        return dict(self._states.get(route, {}))
