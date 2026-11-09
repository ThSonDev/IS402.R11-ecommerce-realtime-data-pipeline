"""Tests for producer/main.py helpers that need no Kafka: time ranges and late events."""
import uuid
from datetime import datetime

import main
import pytest

EVENT_IDS = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"event-{i}")) for i in range(20_000)]


def test_to_raw():
    assert main.to_raw(datetime(2019, 11, 1, 9, 0)) == "2019-11-01 09:00:00 UTC"


def test_day_ranges_split_at_midnight():
    ranges = list(main.day_ranges(datetime(2019, 11, 14, 12), datetime(2019, 11, 16, 6)))
    assert ranges == [
        (datetime(2019, 11, 14, 12), datetime(2019, 11, 15)),
        (datetime(2019, 11, 15), datetime(2019, 11, 16)),
        (datetime(2019, 11, 16), datetime(2019, 11, 16, 6)),
    ]


def test_day_ranges_within_one_day():
    start, end = datetime(2019, 11, 1, 9), datetime(2019, 11, 1, 10)
    assert list(main.day_ranges(start, end)) == [(start, end)]


def test_no_late_events_by_default():
    assert all(main.late_delay(e, 0.0, 60.0) == 0.0 for e in EVENT_IDS)


def test_late_share_matches_rate():
    late = [e for e in EVENT_IDS if main.late_delay(e, 0.01, 60.0) > 0]
    assert len(late) / len(EVENT_IDS) == pytest.approx(0.01, abs=0.003)


def test_late_delay_range():
    late = [d for d in (main.late_delay(e, 0.05, 60.0) for e in EVENT_IDS) if d > 0]
    assert late
    assert all(6.0 <= d <= 60.0 for d in late)


def test_late_delay_is_deterministic():
    first = [main.late_delay(e, 0.05, 60.0) for e in EVENT_IDS]
    assert first == [main.late_delay(e, 0.05, 60.0) for e in EVENT_IDS]
