def format_duration(ms: int) -> str:
    seconds = ms // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def parse_duration_to_ms(value) -> int:
    """Convert a YouTube Music duration value to milliseconds.

    Accepts:
      - int/float seconds (e.g. 215 -> 215000)
      - "MM:SS" / "HH:MM:SS" strings (e.g. "3:35" -> 215000)
      - plain numeric strings (e.g. "215" -> 215000)
    Returns 0 for missing or unparseable values.
    """
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value * 1000)
    text = str(value).strip()
    try:
        if ":" not in text:
            return int(float(text) * 1000)
        total_seconds = 0
        for part in text.split(":"):
            total_seconds = total_seconds * 60 + int(part)
        return total_seconds * 1000
    except (TypeError, ValueError):
        return 0


def format_duration_short(ms: int) -> str:
    seconds = ms // 1000
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


def format_time_ago(dt) -> str:
    from datetime import datetime, timedelta, timezone
    if not dt:
        return "Unknown"
    now = datetime.now(timezone.utc)
    diff = now - dt
    if diff < timedelta(minutes=1):
        return "Just now"
    elif diff < timedelta(hours=1):
        return f"{int(diff.total_seconds() / 60)}m ago"
    elif diff < timedelta(days=1):
        return f"{int(diff.total_seconds() / 3600)}h ago"
    elif diff < timedelta(days=30):
        return f"{int(diff.days)}d ago"
    else:
        return f"{int(diff.days / 30)}mo ago"