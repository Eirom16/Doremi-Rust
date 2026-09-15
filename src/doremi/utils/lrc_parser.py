import re
from dataclasses import dataclass


@dataclass
class LrcLine:
    time_ms: int
    text: str


def parse_lrc(lrc_text: str) -> list[LrcLine]:
    pattern = re.compile(r"\[(\d{2}):(\d{2})\.(\d{2,3})](.*)")
    lines = []
    for match in pattern.finditer(lrc_text):
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        millis_str = match.group(3)
        millis = int(millis_str.ljust(3, "0")[:3])
        time_ms = minutes * 60000 + seconds * 1000 + millis
        text = match.group(4).strip()
        lines.append(LrcLine(time_ms=time_ms, text=text))
    lines.sort(key=lambda x: x.time_ms)
    return lines


def find_current_line(lines: list[LrcLine], position_ms: int) -> int:
    for i, line in enumerate(lines):
        if line.time_ms > position_ms:
            return max(0, i - 1)
    return len(lines) - 1 if lines else -1