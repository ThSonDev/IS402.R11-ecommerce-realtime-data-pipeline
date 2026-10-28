"""Map original 2019 timestamps onto the replay timeline."""
from datetime import datetime, timezone


def parse_raw(raw: str) -> datetime:
    """'2019-11-01 00:00:41 UTC' -> timezone-aware datetime in UTC."""
    return datetime.strptime(raw.removesuffix(" UTC"), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def replay_time(original: datetime, original_start: datetime, replay_start: datetime, speed: float = 1.0) -> datetime:
    """Where an original timestamp lands on the replay timeline.

    original_start maps to replay_start; gaps between events shrink by `speed`.
    """
    return replay_start + (original - original_start) / speed


def to_iso_ms(dt: datetime) -> str:
    """datetime -> '2026-11-11T13:15:03.120Z' (UTC, milliseconds)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"
