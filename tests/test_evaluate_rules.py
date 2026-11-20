"""Tests for analysis/evaluate_rules.py on a hand-made scenario log and alert list."""
import csv

import evaluate_rules
import pytest

LOG = {"scenarios": [
    {"scenario": "bot", "entity_ids": ["900000000", "900000001", "900000002"]},
    {"scenario": "multi_account", "entity_ids": ["dev_a", "dev_b"]},
    {"scenario": "price_glitch", "entity_ids": ["111", "222", "333"]},
    {"scenario": "payment_outage", "entity_ids": [],
     "start": "2026-11-11T13:07:00.000Z", "end": "2026-11-11T13:17:00.000Z"},
]}


def alert(rule, entity, when="2026-11-11T13:01:00Z"):
    return {"alert_time": when, "rule_name": rule, "entity_type": "x", "entity_id": entity,
            "metric_name": "m", "metric_value": 1.0, "threshold": 1.0, "event_id": None}


ALERTS = [
    alert("bot", "900000000"), alert("bot", "900000000"), alert("bot", "900000001"),
    alert("bot", "123456789"),                                     # a real user: false positive
    alert("multi_account", "dev_a"), alert("multi_account", "dev_b"),
    alert("price_glitch", "111"),
    alert("payment_outage", None, "2026-11-11T13:09:00Z"),
    alert("payment_outage", None, "2026-11-11T13:18:30Z"),         # within the 120 s tolerance
    alert("payment_outage", None, "2026-11-11T14:00:00Z"),         # nothing happened then
]


def by_rule(results):
    return {r["rule"]: r for r in results}


def test_entity_rules():
    r = by_rule(evaluate_rules.evaluate(ALERTS, LOG))
    bot = r["bot"]
    assert (bot["alerts"], bot["predicted"], bot["true_positive"]) == (4, 3, 2)
    assert bot["precision"] == pytest.approx(2 / 3)
    assert bot["recall"] == pytest.approx(2 / 3)
    assert bot["false_positive"] == ["123456789"]
    assert bot["missed"] == ["900000002"]
    assert (r["multi_account"]["precision"], r["multi_account"]["recall"]) == (1.0, 1.0)
    assert r["price_glitch"]["precision"] == 1.0
    assert r["price_glitch"]["recall"] == pytest.approx(1 / 3)


def test_window_rule():
    outage = by_rule(evaluate_rules.evaluate(ALERTS, LOG))["payment_outage"]
    assert outage["alerts"] == 3
    assert outage["precision"] == pytest.approx(2 / 3)
    assert outage["recall"] == 1.0
    assert len(outage["false_positive"]) == 1


def test_extra_incident_window_can_be_missed():
    incident = [("2026-11-11T15:00:00Z", "2026-11-11T15:30:00Z")]
    outage = by_rule(evaluate_rules.evaluate(ALERTS, LOG, incident))["payment_outage"]
    assert outage["truth"] == 2
    assert outage["recall"] == 0.5
    assert outage["missed"] == ["2026-11-11T15:00:00+00:00 - 2026-11-11T15:30:00+00:00"]


def test_no_alerts_gives_no_precision():
    r = by_rule(evaluate_rules.evaluate([], LOG))
    assert r["bot"]["precision"] is None
    assert r["bot"]["recall"] == 0.0
    assert "| bot | user | 0 | 3 | 0 | – | 0% |" in evaluate_rules.to_markdown(list(r.values()))


def test_load_alerts_from_csv(tmp_path):
    path = tmp_path / "alerts.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(ALERTS[0]))
        writer.writeheader()
        writer.writerows(ALERTS)
    loaded = evaluate_rules.load_alerts(str(path))
    assert len(loaded) == len(ALERTS)
    assert by_rule(evaluate_rules.evaluate(loaded, LOG))["bot"]["true_positive"] == 2
