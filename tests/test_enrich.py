"""Tests for producer/enrich.py: same input gives the same event, with every field valid."""
import re
import uuid
from itertools import pairwise
from pathlib import Path

import enrich
import pytest

ROOT = Path(__file__).resolve().parent.parent
PROVINCES_CSV = ROOT / "stream" / "reference" / "provinces.csv"

# docs/event-schema.md, section 1
EVENT_FIELDS = {
    "schema_version", "event_id", "event_type", "event_time", "original_time", "sent_time",
    "user_id", "session_id", "order_id", "device_id", "is_new_account", "product_id",
    "category_code", "brand", "price_vnd", "channel", "province_code", "payment_method",
    "voucher_code", "is_fraud", "scenario", "is_late",
}
EVENT_TYPES = {"view", "cart", "purchase"}
CHANNELS = {"tiki", "shopee", "lazada"}
PAYMENT_METHODS = {"cod", "momo", "zalopay", "card"}
ISO_MS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")
ISO_S = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def make_row(**overrides):
    """A raw row shaped like reader.read_events output (the purchase from docs/event-schema.md)."""
    row = {
        "event_time": "2019-11-17 09:15:03 UTC",
        "event_type": "purchase",
        "product_id": 1004856,
        "category_code": "electronics.smartphone",
        "brand": "samsung",
        "price": 128.42,
        "user_id": 512386086,
        "user_session": "0f039697-fedc-40fa-8830-39c1e8a2b9d4",
    }
    row.update(overrides)
    return row


def many_rows(n=20_000):
    """n rows from n different users and sessions, cycling through the three event types."""
    types = ["view", "cart", "purchase"]
    return [
        make_row(user_id=500_000_000 + i, event_type=types[i % 3],
                 user_session=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"session-{i}")))
        for i in range(n)
    ]


def share(events, field, value):
    return sum(ev[field] == value for ev in events) / len(events)


@pytest.fixture(scope="module")
def provinces():
    return enrich.load_provinces(str(PROVINCES_CSV))


@pytest.fixture(scope="module")
def events(provinces):
    return [enrich.enrich(r, provinces) for r in many_rows()]


# --- same input, same output ---------------------------------------------------

def test_same_row_gives_same_event(provinces):
    row = make_row()
    assert enrich.enrich(row, provinces) == enrich.enrich(dict(row), provinces)


def test_seed_changes_simulated_fields_only(provinces, monkeypatch):
    rows = many_rows(200)
    before = [enrich.enrich(r, provinces) for r in rows]
    monkeypatch.setattr(enrich, "SEED", "another-seed")
    after = [enrich.enrich(r, provinces) for r in rows]
    # event_id comes from the row content, not from the seed
    assert [e["event_id"] for e in before] == [e["event_id"] for e in after]
    # simulated fields follow the seed
    assert [e["device_id"] for e in before] != [e["device_id"] for e in after]
    assert [e["channel"] for e in before] != [e["channel"] for e in after]


# --- every field present and valid ----------------------------------------------

def test_event_has_exactly_the_contract_fields(events):
    for ev in events:
        assert set(ev) == EVENT_FIELDS


def test_field_types(events):
    for ev in events:
        assert ev["schema_version"] == 1
        uuid.UUID(ev["event_id"])  # raises if it is not a UUID
        assert isinstance(ev["user_id"], int)
        assert isinstance(ev["product_id"], int)
        assert isinstance(ev["price_vnd"], int)
        assert isinstance(ev["is_new_account"], bool)
        assert ISO_MS.fullmatch(ev["event_time"])
        assert ISO_MS.fullmatch(ev["sent_time"])
        assert ISO_S.fullmatch(ev["original_time"])


def test_values_are_in_allowed_lists(events, provinces):
    codes = set(provinces[0])
    for ev in events:
        assert ev["event_type"] in EVENT_TYPES
        assert ev["channel"] in CHANNELS
        assert ev["province_code"] in codes
        assert ev["payment_method"] in PAYMENT_METHODS | {None}
        assert ev["voucher_code"] in set(enrich.VOUCHER_CODES) | {None}
        assert re.fullmatch(r"dev_[0-9a-f]{12}", ev["device_id"])
        assert ev["is_fraud"] is False
        assert ev["scenario"] is None
        assert ev["is_late"] is False


def test_event_ids_are_unique(events):
    assert len({ev["event_id"] for ev in events}) == len(events)


def test_provinces_csv_has_34_unique_codes(provinces):
    codes, cumulative = provinces
    assert len(codes) == 34
    assert len(set(codes)) == 34
    assert cumulative[-1] == 1.0


@pytest.mark.parametrize("event_type", ["view", "cart"])
def test_order_fields_only_on_purchase(provinces, event_type):
    ev = enrich.enrich(make_row(event_type=event_type), provinces)
    assert ev["order_id"] is None
    assert ev["payment_method"] is None
    assert ev["voucher_code"] is None


def test_purchase_has_order_id_from_session(provinces):
    ev = enrich.enrich(make_row(), provinces)
    assert ev["order_id"] == "o_0f039697fedc"
    assert ev["payment_method"] in PAYMENT_METHODS


# --- simulated fields stick to the right entity -----------------------------------

def test_user_fields_stay_with_the_user(provinces):
    a = enrich.enrich(make_row(), provinces)
    b = enrich.enrich(make_row(event_type="view", event_time="2019-11-20 01:02:03 UTC",
                               user_session="11111111-2222-3333-4444-555555555555"), provinces)
    for field in ("channel", "province_code", "device_id", "is_new_account"):
        assert a[field] == b[field]


def test_order_fields_shared_within_a_session(provinces):
    a = enrich.enrich(make_row(product_id=1004856), provinces)
    b = enrich.enrich(make_row(product_id=1005115, price=900.0), provinces)
    for field in ("order_id", "payment_method", "voucher_code"):
        assert a[field] == b[field]
    assert a["event_id"] != b["event_id"]


# --- conversions -----------------------------------------------------------------

def test_time_fields(provinces):
    ev = enrich.enrich(make_row(), provinces)
    assert ev["original_time"] == "2019-11-17T09:15:03Z"
    assert ev["event_time"] == "2019-11-17T09:15:03.000Z"  # default: the original time
    assert ev["sent_time"] == ev["event_time"]

    ev = enrich.enrich(make_row(), provinces,
                       event_time="2026-11-11T13:15:03.120Z", sent_time="2026-11-11T13:15:03.150Z")
    assert ev["event_time"] == "2026-11-11T13:15:03.120Z"
    assert ev["sent_time"] == "2026-11-11T13:15:03.150Z"
    assert ev["original_time"] == "2019-11-17T09:15:03Z"


@pytest.mark.parametrize(("price", "expected"), [(128.42, 3_319_657), (0.0, 0), (None, 0)])
def test_price_vnd(provinces, price, expected):
    assert enrich.enrich(make_row(price=price), provinces)["price_vnd"] == expected


# --- shares match the configured weights -------------------------------------------

def test_channel_shares(events):
    total = sum(w for _, w in enrich.CHANNELS)
    for name, weight in enrich.CHANNELS:
        assert share(events, "channel", name) == pytest.approx(weight / total, abs=0.02)


def test_payment_shares(events):
    purchases = [ev for ev in events if ev["event_type"] == "purchase"]
    total = sum(w for _, w in enrich.PAYMENT_METHODS)
    for name, weight in enrich.PAYMENT_METHODS:
        assert share(purchases, "payment_method", name) == pytest.approx(weight / total, abs=0.03)


def test_new_account_share(events):
    assert share(events, "is_new_account", True) == pytest.approx(enrich.NEW_ACCOUNT_RATE, abs=0.01)


def test_province_follows_population(events, provinces):
    codes, cumulative = provinces
    weights = [cumulative[0]] + [b - a for a, b in pairwise(cumulative)]
    for code, weight in zip(codes, weights):
        assert share(events, "province_code", code) == pytest.approx(weight, abs=0.01)
