"""Tests for functions/fraud_alert: formatting, collapsing, dedup and the HTTP entry point (no real Telegram)."""
import json

import alerts
import azure.functions as func
import function_app
import pytest


def alert(rule="bot", entity_type="user", entity_id="900000000", value=20.0, threshold=5.0,
          when="2026-11-11T13:01:00.0000000Z"):
    return {"alert_time": when, "rule_name": rule, "entity_type": entity_type, "entity_id": entity_id,
            "metric_name": "orders_per_minute", "metric_value": value, "threshold": threshold, "event_id": None}


class Clock:
    def __init__(self):
        self.now = 1_000.0

    def __call__(self):
        return self.now


# --- formatting ------------------------------------------------------------------

def test_format_user_alert():
    line = alerts.format_alert(alert())
    assert line == "• Bot gom hàng - user 900000000: orders_per_minute = 20 (ngưỡng 5)"


def test_format_system_alert_and_decimals():
    line = alerts.format_alert(alert("payment_outage", "system", None, 57.5, 90))
    assert line == "• Số đơn bất thường - system: orders_per_minute = 57.50 (ngưỡng 90)"


def test_header_uses_latest_alert_time_in_vietnam_time():
    batch = [alert(when="2026-11-11T13:01:00Z"), alert("price_glitch", "product", "26201045",
                                                       when="2026-11-11T13:05:30.1234567Z")]
    (message,) = alerts.build_messages(batch)
    assert message.splitlines()[0] == "🚨 2 cảnh báo lúc 20:05 11/11 (giờ VN)"
    assert len(message.splitlines()) == 3


def test_long_batches_are_split_under_the_telegram_limit():
    batch = [alert(entity_id=str(900_000_000 + i)) for i in range(200)]
    messages = alerts.build_messages(batch)
    assert len(messages) > 1
    assert all(len(m) <= alerts.MAX_MESSAGE for m in messages)
    assert sum(len(m.splitlines()) - 1 for m in messages) == 200   # every alert appears once


def test_no_alerts_no_message():
    assert alerts.build_messages([]) == []


# --- collapsing and dedup --------------------------------------------------------

def test_collapse_keeps_strongest_and_counts_repeats():
    merged = alerts.collapse([alert(value=12), alert(value=20), alert(value=7), alert(entity_id="900000001")])
    by_entity = {a["entity_id"]: a for a in merged}
    assert len(merged) == 2
    assert by_entity["900000000"]["metric_value"] == 20
    assert by_entity["900000000"]["repeats"] == 3
    assert by_entity["900000001"]["repeats"] == 1


def test_deduper_drops_repeats_within_the_window():
    clock = Clock()
    deduper = alerts.Deduper(window=600, clock=clock)
    assert len(deduper.fresh([alert()])) == 1
    clock.now += 300
    assert deduper.fresh([alert()]) == []                      # same rule + entity, too soon
    assert len(deduper.fresh([alert(entity_id="x")])) == 1     # another entity is new
    clock.now += 301
    assert len(deduper.fresh([alert()])) == 1                  # window passed


def test_handle_sends_one_message_per_batch():
    sent = []
    deduper = alerts.Deduper(clock=Clock())
    n = alerts.handle([alert(), alert(value=9), alert("multi_account", "device", "dev_x")], deduper,
                      "token", "chat", send=lambda *args: sent.append(args))
    assert n == 1
    assert len(sent) == 1
    token, chat, text = sent[0]
    assert (token, chat) == ("token", "chat")
    assert "Bot gom hàng" in text and "dev_x" in text
    assert alerts.handle([alert()], deduper, "token", "chat", send=lambda *args: sent.append(args)) == 0


def test_send_telegram_posts_json():
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{}"

    def opener(request, timeout):
        calls.append((request.full_url, json.loads(request.data), timeout))
        return Response()

    alerts.send_telegram("123:abc", "-100", "hello", opener=opener)
    assert calls == [("https://api.telegram.org/bot123:abc/sendMessage",
                      {"chat_id": "-100", "text": "hello", "disable_web_page_preview": True}, 10)]


# --- HTTP entry point ------------------------------------------------------------

@pytest.fixture
def call(monkeypatch):
    monkeypatch.setattr(function_app, "deduper", alerts.Deduper(clock=Clock()))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    user_function = function_app.fraud_alert.build().get_user_function()

    def post(body):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        return user_function(func.HttpRequest("POST", "/api/fraud_alert", body=data))
    return post


def test_http_batch_is_sent(call, monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send_telegram", lambda *args: sent.append(args))
    response = call([alert(), alert("price_glitch", "product", "26201045")])
    assert response.status_code == 200
    assert json.loads(response.get_body()) == {"received": 2, "messages_sent": 1}
    assert len(sent) == 1


def test_http_empty_batch_is_ok(call):
    assert call([]).status_code == 200


def test_http_bad_json_is_rejected(call):
    assert call(b"not json").status_code == 400


def test_http_telegram_failure_still_answers_200(call, monkeypatch):
    def boom(*args):
        raise OSError("telegram down")
    monkeypatch.setattr(alerts, "send_telegram", boom)
    response = call([alert()])
    assert response.status_code == 200
    assert json.loads(response.get_body())["messages_sent"] == 0
