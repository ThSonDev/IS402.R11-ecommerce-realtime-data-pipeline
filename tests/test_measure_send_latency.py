"""Percentile math of scripts/measure_send_latency.py (no broker needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure_send_latency as m


def test_percentile_nearest_rank():
    values = list(range(1, 101))
    assert m.percentile(values, 50) == 50
    assert m.percentile(values, 95) == 95
    assert m.percentile(values, 99) == 99
    assert m.percentile([7.0], 99) == 7.0


def test_summarize_counts_failures():
    out = m.summarize([10.0, 20.0, 30.0, 40.0], failed=2)
    assert out["acked"] == 4 and out["failed"] == 2 and out["mean"] == 25.0
    assert m.summarize([], failed=3) == {"acked": 0, "failed": 3}
