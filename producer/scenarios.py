"""Labelled fraud and incident scenarios mixed into the replay (docs/event-schema.md).

Each enabled scenario starts at a fixed number of seconds into the replay timeline, one
after another, so the same arguments always produce the same events. Injected events
carry is_fraud=true and scenario=<name>. payment_outage removes real purchases instead,
so its ground truth is a time window, written to the scenario log with the others.
"""
import csv
import uuid
from dataclasses import dataclass, field

import enrich

SCENARIOS = ("bot", "multi_account", "price_glitch", "payment_outage")
SPACING = 120  # seconds between the starts of two consecutive scenarios

# Simulation parameters. Baselines from the real data (analysis/eda.py):
# a real user places at most 7 orders in one minute (99.7% of user-minutes have 1),
# and a product's price varies up to 1.67x (p99 of max/min).
BOT_USERS = 3
BOT_ORDERS = 20             # orders per bot user ...
BOT_SECONDS = 60            # ... within this many seconds
MULTI_DEVICES = 2
MULTI_ACCOUNTS = 6          # new accounts per shared device ...
MULTI_SECONDS = 300         # ... within this many seconds (rule 2 looks at 10 minutes)
MULTI_VOUCHER = "NEWMEMBER"
GLITCH_PRODUCTS = 3
GLITCH_ORDERS = 5           # orders per glitched product ...
GLITCH_SECONDS = 120        # ... within this many seconds
GLITCH_SHARE = (0.1, 0.3)   # sold at 10-30% of the reference price
GLITCH_MIN_REF_VND = 5_000_000
OUTAGE_METHOD = "cod"       # largest payment share (40%), so the dip is visible
OUTAGE_SECONDS = 600

# Fake user ids sit above the real ones (max 579,969,851 in November 2019).
FAKE_USER_BASE = {"bot": 900_000_000, "multi_account": 910_000_000, "price_glitch": 920_000_000}
_SESSION_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "ecommerce-realtime-data-pipeline/scenarios")


@dataclass
class Injection:
    """One injected event: when it is due, the raw-like row, and fields set after enrich."""
    due: float
    row: dict
    overrides: dict


@dataclass
class Plan:
    """What the enabled scenarios add to (or remove from) one replay."""
    injections: list = field(default_factory=list)
    outage: tuple | None = None      # (start due, end due, payment method)
    log: list = field(default_factory=list)


def load_ref_prices(path: str) -> list[tuple[int, int]]:
    """price_list.csv -> [(product_id, ref_price_vnd)], sorted by product_id."""
    with open(path, newline="", encoding="utf-8") as f:
        return sorted((int(r["product_id"]), int(r["ref_price_vnd"])) for r in csv.DictReader(f))


def _pick(items, n, *parts):
    """n distinct items chosen by hash, so the choice is the same on every replay."""
    ranked = sorted(items, key=lambda item: enrich._unit(*parts, item[0]))
    return ranked[:n]


def _session(*parts) -> str:
    return str(uuid.uuid5(_SESSION_NAMESPACE, "|".join(map(str, parts))))


def _row(original_at, due, event_type, product_id, ref_vnd, user_id, session, price_share=1.0):
    return {
        "event_time": original_at(due),
        "event_type": event_type,
        "product_id": product_id,
        "category_code": None,
        "brand": None,
        "price": ref_vnd * price_share / enrich.USD_VND,
        "user_id": user_id,
        "user_session": session,
    }


def _bot(start, original_at, products):
    picks = _pick(products, BOT_USERS * BOT_ORDERS, "bot_product")
    injections, users = [], []
    for b in range(BOT_USERS):
        user = FAKE_USER_BASE["bot"] + b
        users.append(user)
        for k in range(BOT_ORDERS):
            due = start + BOT_SECONDS * k / BOT_ORDERS
            product, ref = picks[b * BOT_ORDERS + k]
            row = _row(original_at, due, "purchase", product, ref, user, _session("bot", b, k))
            injections.append(Injection(due, row, {"is_fraud": True, "scenario": "bot"}))
    entry = {"entity_type": "user", "entity_ids": [str(u) for u in users]}
    return injections, start + BOT_SECONDS, entry


def _multi_account(start, original_at, products):
    picks = _pick(products, MULTI_DEVICES * MULTI_ACCOUNTS, "multi_product")
    injections, devices = [], []
    for d in range(MULTI_DEVICES):
        device = "dev_" + enrich._digest("multi_device", d).hex()[:12]
        devices.append(device)
        for a in range(MULTI_ACCOUNTS):
            idx = d * MULTI_ACCOUNTS + a
            due = start + MULTI_SECONDS * idx / (MULTI_DEVICES * MULTI_ACCOUNTS)
            user = FAKE_USER_BASE["multi_account"] + idx
            product, ref = picks[idx]
            row = _row(original_at, due, "purchase", product, ref, user, _session("multi", d, a))
            overrides = {"device_id": device, "is_new_account": True, "voucher_code": MULTI_VOUCHER,
                         "is_fraud": True, "scenario": "multi_account"}
            injections.append(Injection(due, row, overrides))
    entry = {"entity_type": "device", "entity_ids": devices, "voucher_code": MULTI_VOUCHER}
    return injections, start + MULTI_SECONDS, entry


def _price_glitch(start, original_at, products):
    expensive = [p for p in products if p[1] >= GLITCH_MIN_REF_VND]
    picks = _pick(expensive, GLITCH_PRODUCTS, "glitch_product")
    low, high = GLITCH_SHARE
    injections = []
    for g, (product, ref) in enumerate(picks):
        for k in range(GLITCH_ORDERS):
            idx = g * GLITCH_ORDERS + k
            due = start + GLITCH_SECONDS * idx / (GLITCH_PRODUCTS * GLITCH_ORDERS)
            share = low + (high - low) * enrich._unit("glitch_share", product, k)
            user = FAKE_USER_BASE["price_glitch"] + idx
            row = _row(original_at, due, "purchase", product, ref, user, _session("glitch", g, k), share)
            injections.append(Injection(due, row, {"is_fraud": True, "scenario": "price_glitch"}))
    entry = {"entity_type": "product", "entity_ids": [str(p) for p, _ in picks],
             "ref_price_vnd": {str(p): ref for p, ref in picks}}
    return injections, start + GLITCH_SECONDS, entry


def build(names, first_start, original_at, products, outage_seconds=OUTAGE_SECONDS) -> Plan:
    """Plan the enabled scenarios, in SCENARIOS order, starting at `first_start` seconds.

    original_at(due) gives the dataset-time string ('2019-11-01 09:00:00 UTC') for a due time,
    used as original_time of injected events.
    """
    unknown = set(names) - set(SCENARIOS)
    if unknown:
        raise ValueError(f"unknown scenarios: {', '.join(sorted(unknown))}")
    plan = Plan()
    builders = {"bot": _bot, "multi_account": _multi_account, "price_glitch": _price_glitch}
    enabled = [s for s in SCENARIOS if s in names]
    for n, name in enumerate(enabled):
        start = first_start + SPACING * n
        if name == "payment_outage":
            end = start + outage_seconds
            plan.outage = (start, end, OUTAGE_METHOD)
            entry = {"entity_type": "system", "entity_ids": [], "payment_method": OUTAGE_METHOD}
        else:
            injections, end, entry = builders[name](start, original_at, products)
            plan.injections.extend(injections)
            entry["events"] = len(injections)
        plan.log.append({"scenario": name, "start_due": start, "end_due": end, **entry})
    plan.injections.sort(key=lambda inj: inj.due)
    return plan
