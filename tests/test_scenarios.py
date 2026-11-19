"""Tests for producer/scenarios.py and the scenario path of producer/main.py (file mode, no Kafka)."""
import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import enrich
import main
import pytest
import scenarios

ROOT = Path(__file__).resolve().parent.parent
REF_PRICES = ROOT / "stream" / "reference" / "price_list.csv"
PROVINCES_CSV = ROOT / "stream" / "reference" / "provinces.csv"
REAL_MAX_USER_ID = 579_969_851
REAL_MAX_ORDERS_PER_MINUTE = 7


def original_at(due):
    return main.to_raw(datetime(2019, 11, 1, 9) + timedelta(seconds=due))


@pytest.fixture(scope="module")
def products():
    return scenarios.load_ref_prices(str(REF_PRICES))


@pytest.fixture(scope="module")
def provinces():
    return enrich.load_provinces(str(PROVINCES_CSV))


@pytest.fixture(scope="module")
def plan(products):
    return scenarios.build(list(scenarios.SCENARIOS), 60, original_at, products)


def by_scenario(plan):
    groups = defaultdict(list)
    for inj in plan.injections:
        groups[inj.overrides["scenario"]].append(inj)
    return groups


def enriched(injections, provinces):
    return [{**enrich.enrich(inj.row, provinces), **inj.overrides} for inj in injections]


# --- plan ------------------------------------------------------------------------

def test_unknown_scenario_is_rejected(products):
    with pytest.raises(ValueError):
        scenarios.build(["bot", "nope"], 60, original_at, products)


def test_scenarios_start_one_after_another(plan):
    starts = {e["scenario"]: e["start_due"] for e in plan.log}
    assert starts == {name: 60 + scenarios.SPACING * n for n, name in enumerate(scenarios.SCENARIOS)}


def test_plan_is_deterministic(plan, products):
    again = scenarios.build(list(scenarios.SCENARIOS), 60, original_at, products)
    assert [(i.due, i.row, i.overrides) for i in again.injections] == \
           [(i.due, i.row, i.overrides) for i in plan.injections]


def test_injections_are_sorted_and_labelled(plan):
    dues = [i.due for i in plan.injections]
    assert dues == sorted(dues)
    for inj in plan.injections:
        assert inj.overrides["is_fraud"] is True
        assert inj.overrides["scenario"] in scenarios.SCENARIOS
        assert inj.row["user_id"] > REAL_MAX_USER_ID   # fake users never clash with real ones


def test_only_enabled_scenarios_are_built(products):
    plan = scenarios.build(["price_glitch"], 30, original_at, products)
    assert {i.overrides["scenario"] for i in plan.injections} == {"price_glitch"}
    assert plan.outage is None
    assert [e["start_due"] for e in plan.log] == [30]


# --- each scenario ---------------------------------------------------------------

def test_bot_users_order_far_above_the_real_maximum(plan, provinces):
    events = enriched(by_scenario(plan)["bot"], provinces)
    assert len(events) == scenarios.BOT_USERS * scenarios.BOT_ORDERS
    orders = defaultdict(set)
    for ev in events:
        assert ev["event_type"] == "purchase"
        orders[ev["user_id"]].add(ev["order_id"])
    assert len(orders) == scenarios.BOT_USERS
    for user_orders in orders.values():
        assert len(user_orders) == scenarios.BOT_ORDERS > REAL_MAX_ORDERS_PER_MINUTE
    span = max(i.due for i in by_scenario(plan)["bot"]) - min(i.due for i in by_scenario(plan)["bot"])
    assert span < 60   # all of a bot's orders fall within one minute


def test_multi_account_shares_devices_and_voucher(plan, provinces):
    events = enriched(by_scenario(plan)["multi_account"], provinces)
    accounts = defaultdict(set)
    for ev in events:
        assert ev["is_new_account"] is True
        assert ev["voucher_code"] == scenarios.MULTI_VOUCHER
        accounts[ev["device_id"]].add(ev["user_id"])
    assert len(accounts) == scenarios.MULTI_DEVICES
    assert all(len(users) == scenarios.MULTI_ACCOUNTS for users in accounts.values())
    dues = [i.due for i in by_scenario(plan)["multi_account"]]
    assert max(dues) - min(dues) < 600   # inside rule 2's 10-minute window


def test_price_glitch_sells_far_below_reference(plan, provinces, products):
    ref = dict(products)
    events = enriched(by_scenario(plan)["price_glitch"], provinces)
    assert len(events) == scenarios.GLITCH_PRODUCTS * scenarios.GLITCH_ORDERS
    assert len({ev["product_id"] for ev in events}) == scenarios.GLITCH_PRODUCTS
    low, high = scenarios.GLITCH_SHARE
    for ev in events:
        assert ref[ev["product_id"]] >= scenarios.GLITCH_MIN_REF_VND
        assert low - 0.001 <= ev["price_vnd"] / ref[ev["product_id"]] <= high + 0.001


def test_payment_outage_is_a_window(plan):
    start, end, method = plan.outage
    assert start == 60 + scenarios.SPACING * 3
    assert end - start == scenarios.OUTAGE_SECONDS
    assert method == scenarios.OUTAGE_METHOD
    assert "payment_outage" not in by_scenario(plan)   # no events are injected for it


# --- whole replay in file mode ---------------------------------------------------

def fake_rows(minutes=30):
    """One real-looking event per second; every third one is a purchase."""
    start = datetime(2019, 11, 1, 9)
    for s in range(minutes * 60):
        yield {
            "event_time": main.to_raw(start + timedelta(seconds=s)),
            "event_type": "purchase" if s % 3 == 0 else "view",
            "product_id": 1000365,
            "category_code": "electronics.smartphone",
            "brand": "samsung",
            "price": 100.0,
            "user_id": 100_000_000 + s,
            "user_session": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"fake-session-{s}")),
        }


def test_replay_to_file_with_all_scenarios(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(main, "iter_rows", lambda args: fake_rows())
    out = tmp_path / "events.json"
    args = main.parse_args(["--start", "2019-11-01T09:00", "--end", "2019-11-01T09:30", "--speed", "1",
                            "--scenarios", "all", "--out", str(out), "--replay-start", "2026-11-11T13:00"])
    main.run(args)

    events = [json.loads(line) for line in out.read_text().splitlines()]
    counts = Counter(ev["scenario"] for ev in events)
    assert counts["bot"] == scenarios.BOT_USERS * scenarios.BOT_ORDERS
    assert counts["multi_account"] == scenarios.MULTI_DEVICES * scenarios.MULTI_ACCOUNTS
    assert counts["price_glitch"] == scenarios.GLITCH_PRODUCTS * scenarios.GLITCH_ORDERS
    assert all(ev["is_fraud"] == (ev["scenario"] is not None) for ev in events)
    assert events[0]["event_time"].startswith("2026-11-11T13:00:00")

    log = json.loads(out.with_suffix(".scenarios.json").read_text())
    entries = {e["scenario"]: e for e in log["scenarios"]}
    assert set(entries) == set(scenarios.SCENARIOS)
    assert not [k for e in log["scenarios"] for k in e if k.endswith("_due")]   # internal keys stay out
    outage = entries["payment_outage"]
    assert outage["start"] == "2026-11-11T13:07:00.000Z"   # 60 + 3 x 120 seconds in
    assert outage["dropped_purchases"] > 0
    in_outage = [ev for ev in events if outage["start"] <= ev["event_time"] < outage["end"]]
    assert not [ev for ev in in_outage if ev["scenario"] is None and ev["event_type"] == "purchase"
                and ev["payment_method"] == outage["payment_method"]]
    assert len(events) == 30 * 60 + sum(counts[s] for s in scenarios.SCENARIOS) - outage["dropped_purchases"]
