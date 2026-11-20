"""Turn Stream Analytics alert batches into short Telegram messages (docs/event-schema.md, `alerts`).

Kept free of Azure imports so it can be tested and run locally:
    python functions/fraud_alert/alerts.py            # print a sample message
    python functions/fraud_alert/alerts.py --send     # send it, with TELEGRAM_* from .env
"""
import json
import os
import sys
import time
import urllib.request
from datetime import UTC, datetime, timedelta

RULE_LABELS = {
    "bot": "Bot gom hàng",
    "multi_account": "Nhiều tài khoản mới / 1 thiết bị",
    "price_glitch": "Sai giá",
    "payment_outage": "Số đơn bất thường",
}
VN_TIME = timedelta(hours=7)
SUPPRESS_SECONDS = 600   # same rule + entity again within this window: not re-sent
MAX_MESSAGE = 4096       # Telegram limit per message
TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"


def parse_time(text) -> datetime | None:
    """ASA ISO time ('2026-11-11T13:01:00.0000000Z') -> aware UTC datetime; None if missing."""
    if not text:
        return None
    return datetime.strptime(str(text)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)


def alert_key(alert: dict) -> tuple:
    return alert.get("rule_name"), alert.get("entity_type"), alert.get("entity_id")


def collapse(batch: list) -> list:
    """One alert per rule + entity: keep the strongest, count how many times it fired."""
    merged = {}
    for alert in batch:
        key = alert_key(alert)
        if key not in merged:
            merged[key] = {**alert, "repeats": 1}
            continue
        best = merged[key]
        repeats = best["repeats"] + 1
        if (alert.get("metric_value") or 0) > (best.get("metric_value") or 0):
            best = {**alert}
        merged[key] = {**best, "repeats": repeats}
    return list(merged.values())


class Deduper:
    """Drops alerts already sent within `window` seconds.

    Memory only: one Functions instance remembers what it sent; a cold start forgets.
    Good enough to stop repeats within a burst; dbo.alerts keeps the full history.
    """

    def __init__(self, window: float = SUPPRESS_SECONDS, clock=time.time):
        self.window = window
        self.clock = clock
        self.last_sent = {}

    def fresh(self, alerts: list) -> list:
        now = self.clock()
        new = [a for a in alerts if now - self.last_sent.get(alert_key(a), -self.window) >= self.window]
        for alert in new:
            self.last_sent[alert_key(alert)] = now
        return new


def _number(value) -> str:
    if value is None:
        return "?"
    value = float(value)
    return f"{value:,.0f}" if value == int(value) else f"{value:,.2f}"


def format_alert(alert: dict) -> str:
    """'• Bot gom hàng - user 900000000: orders_per_minute = 20 (ngưỡng 5)'"""
    rule = RULE_LABELS.get(alert.get("rule_name"), alert.get("rule_name") or "?")
    entity = alert.get("entity_type") or "?"
    if alert.get("entity_id"):
        entity = f"{entity} {alert['entity_id']}"
    line = (f"• {rule} - {entity}: {alert.get('metric_name') or 'value'} = "
            f"{_number(alert.get('metric_value'))} (ngưỡng {_number(alert.get('threshold'))})")
    if alert.get("repeats", 1) > 1:
        line += f", {alert['repeats']} lần"
    return line


def build_messages(alerts: list) -> list:
    """Header + one line per alert, split so no message exceeds Telegram's limit."""
    if not alerts:
        return []
    times = [t for t in (parse_time(a.get("alert_time")) for a in alerts) if t]
    when = f" lúc {(max(times) + VN_TIME):%H:%M %d/%m} (giờ VN)" if times else ""
    header = f"🚨 {len(alerts)} cảnh báo{when}"
    messages, current = [], header
    for line in (format_alert(a) for a in alerts):
        if len(current) + 1 + len(line) > MAX_MESSAGE:
            messages.append(current)
            current = header + " (tiếp)"
        current += "\n" + line
    messages.append(current)
    return messages


def send_telegram(token: str, chat_id: str, text: str, opener=urllib.request.urlopen) -> None:
    body = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode()
    request = urllib.request.Request(TELEGRAM_URL.format(token=token), data=body,
                                     headers={"Content-Type": "application/json"})
    with opener(request, timeout=10) as response:
        response.read()


def handle(batch: list, deduper: Deduper, token: str, chat_id: str, send=None) -> int:
    """Collapse, drop recent repeats, send. Returns the number of messages sent."""
    send = send or send_telegram   # looked up at call time, so tests can replace it
    messages = build_messages(deduper.fresh(collapse(batch)))
    for text in messages:
        send(token, chat_id, text)
    return len(messages)


SAMPLE = [
    {"alert_time": "2026-11-11T13:01:00.000Z", "rule_name": "bot", "entity_type": "user",
     "entity_id": "900000000", "metric_name": "orders_per_minute", "metric_value": 20, "threshold": 5,
     "event_id": None},
    {"alert_time": "2026-11-11T13:01:00.000Z", "rule_name": "bot", "entity_type": "user",
     "entity_id": "900000000", "metric_name": "orders_per_minute", "metric_value": 12, "threshold": 5,
     "event_id": None},
    {"alert_time": "2026-11-11T13:10:00.000Z", "rule_name": "payment_outage", "entity_type": "system",
     "entity_id": None, "metric_name": "orders_per_minute", "metric_value": 57, "threshold": 90,
     "event_id": None},
]

if __name__ == "__main__":
    texts = build_messages(collapse(SAMPLE))
    if "--send" not in sys.argv:
        print("\n\n".join(texts))
        sys.exit(0)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        sys.exit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env first")
    for text in texts:
        send_telegram(token, chat, text)
    print(f"sent {len(texts)} message(s)")
