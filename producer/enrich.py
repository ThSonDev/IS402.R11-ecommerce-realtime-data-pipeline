"""Turn a raw REES46 row into a full event dict following docs/event-schema.md.

Everything here is deterministic: the same row always gives the same event, so a
replay with the same parameters produces the same data.
"""
import csv
import hashlib
import uuid
from bisect import bisect

SCHEMA_VERSION = 1
SEED = "IS402R11"  # change it and every simulated field changes with it

# USD -> VND, fixed so replays are reproducible.
# Source: Wise mid-market rate (https://wise.com/vn/currency-converter/usd-to-vnd-rate), taken 2026-10-23 09:00 (UTC+7).
USD_VND = 25_850

# Simulation assumptions (name, weight). Keep them in the report.
CHANNELS = [("shopee", 6), ("lazada", 3), ("tiki", 1)]
PAYMENT_METHODS = [("cod", 4), ("momo", 3), ("zalopay", 2), ("card", 1)]
NEW_ACCOUNT_RATE = 0.03
VOUCHER_RATE = 0.2
VOUCHER_CODES = ["FLASH70", "FREESHIP", "FLASH50", "NEWMEMBER", "STUDENT20"]

# Columns of the raw row, in the order used to build event_id.
ROW_COLUMNS = (
    "event_time", "event_type", "product_id", "category_code",
    "brand", "price", "user_id", "user_session",
)
_EVENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "ecommerce-realtime-data-pipeline")


def _digest(*parts) -> bytes:
    # hashlib, not hash(): the built-in hash() of a str changes on every run
    key = "|".join([SEED, *map(str, parts)])
    return hashlib.sha256(key.encode()).digest()


def _unit(*parts) -> float:
    """Deterministic float in [0, 1) derived from the seed and the parts."""
    return int.from_bytes(_digest(*parts)[:8], "big") / 2**64


def _cumulative(weights) -> list[float]:
    """[3, 2, 5] -> [0.3, 0.5, 1.0]"""
    total = sum(weights)
    running = 0
    result = []
    for w in weights:
        running += w
        result.append(running / total)
    return result


def _pick(values, cumulative, u):
    return values[bisect(cumulative, u)]


_CHANNEL_NAMES = [name for name, _ in CHANNELS]
_CHANNEL_CUM = _cumulative([w for _, w in CHANNELS])
_PAYMENT_NAMES = [name for name, _ in PAYMENT_METHODS]
_PAYMENT_CUM = _cumulative([w for _, w in PAYMENT_METHODS])


def load_provinces(path: str):
    """Read provinces.csv -> (province codes, cumulative population weights)."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    codes = [r["province_code"] for r in rows]
    cumulative = _cumulative([int(r["population"]) for r in rows])
    return codes, cumulative


def _iso_time(raw: str) -> str:
    # '2019-11-01 00:00:41 UTC' -> '2019-11-01T00:00:41Z'
    return raw.removesuffix(" UTC").replace(" ", "T") + "Z"


def enrich(row: dict, provinces, event_time: str | None = None, sent_time: str | None = None) -> dict:
    """Build one event from a raw row.

    event_time / sent_time default to the original time; the replay code
    passes the shifted times in.
    """
    user_id = row["user_id"]
    session_id = row["user_session"]
    is_purchase = row["event_type"] == "purchase"

    original_time = _iso_time(row["event_time"])
    event_time = event_time or original_time[:-1] + ".000Z"
    sent_time = sent_time or event_time

    codes, cumulative = provinces
    event_key = "|".join(str(row[c]) for c in ROW_COLUMNS)

    payment_method = None
    voucher_code = None
    if is_purchase:
        payment_method = _pick(_PAYMENT_NAMES, _PAYMENT_CUM, _unit("payment", session_id))
        if _unit("voucher", session_id) < VOUCHER_RATE:
            idx = int(_unit("voucher_code", session_id) * len(VOUCHER_CODES))
            voucher_code = VOUCHER_CODES[idx]

    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid5(_EVENT_NAMESPACE, event_key)),
        "event_type": row["event_type"],
        "event_time": event_time,
        "original_time": original_time,
        "sent_time": sent_time,
        "user_id": user_id,
        "session_id": session_id,
        "order_id": "o_" + session_id.replace("-", "")[:12] if is_purchase else None,
        "device_id": "dev_" + _digest("device", user_id).hex()[:12],
        "is_new_account": _unit("new_account", user_id) < NEW_ACCOUNT_RATE,
        "product_id": row["product_id"],
        "category_code": row["category_code"],
        "brand": row["brand"],
        "price_vnd": round((row["price"] or 0) * USD_VND),
        "channel": _pick(_CHANNEL_NAMES, _CHANNEL_CUM, _unit("channel", user_id)),
        "province_code": _pick(codes, cumulative, _unit("province", user_id)),
        "payment_method": payment_method,
        "voucher_code": voucher_code,
        "is_fraud": False,
        "scenario": None,
        "is_late": False,
    }