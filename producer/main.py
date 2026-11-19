"""Replay REES46 events into Kafka / Event Hubs, optionally with labelled fraud scenarios.

Run from the repo root, for example:
    python producer/main.py --start 2019-11-01T09:00 --end 2019-11-01T10:00 --speed 4
    python producer/main.py --start 2019-11-01T09:00 --end 2019-11-01T10:00 --rate 500
    python producer/main.py --start 2019-11-01T09:00 --end 2019-11-01T10:00 --speed 4 --late-rate 0.01
    python producer/main.py --start 2019-11-01T09:00 --end 2019-11-01T10:00 --speed 4 --scenarios all
    python producer/main.py ... --out events.json --replay-start 2026-11-11T13:00   # file, no Kafka
Kafka settings come from .env (see .env.example).
"""
import argparse
import heapq
import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import enrich
import reader
import scenarios
import timeshift
from confluent_kafka import Producer
from dotenv import load_dotenv

DATA = "data/processed/2019-Nov.parquet"
PROVINCES = "stream/reference/provinces.csv"
PRICE_LIST = "stream/reference/price_list.csv"
SCENARIO_LOG_DIR = "data/scenario_logs"
LOG_EVERY = 10_000
LATE_MIN_SHARE = 0.1  # a late event is held back between 10% and 100% of --late-delay
QUEUE_MAX_MESSAGES = 10_000


def to_raw(dt: datetime) -> str:
    """datetime -> '2019-11-01 09:00:00 UTC', the format reader.read_events expects."""
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def parse_scenarios(text: str) -> list[str]:
    """'all' or a comma-separated list of scenario names."""
    names = list(scenarios.SCENARIOS) if text == "all" else [s for s in text.split(",") if s]
    unknown = set(names) - set(scenarios.SCENARIOS)
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown scenario(s): {', '.join(sorted(unknown))}")
    return names


def utc_time(text: str) -> datetime:
    """ISO time; without an offset it is taken as UTC."""
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Replay REES46 events into Kafka.")
    parser.add_argument("--start", required=True, type=datetime.fromisoformat,
                        help="start of the dataset range (UTC), e.g. 2019-11-01T09:00")
    parser.add_argument("--end", required=True, type=datetime.fromisoformat,
                        help="end of the dataset range (UTC, exclusive)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--speed", type=float, help="replay N times faster, keeping the gaps between events")
    mode.add_argument("--rate", type=float, help="send a fixed N events per second (benchmarks)")
    parser.add_argument("--sample-rate", type=float, default=1.0,
                        help="keep all events of this share of users (0-1], default 1.0")
    parser.add_argument("--late-rate", type=float, default=0.0,
                        help="share of events sent late on purpose, labelled is_late=true (default 0)")
    parser.add_argument("--late-delay", type=float, default=60.0,
                        help="max seconds a late event is held back (default 60)")
    parser.add_argument("--scenarios", type=parse_scenarios, default=[],
                        help=f"'all' or comma-separated: {','.join(scenarios.SCENARIOS)} (default none)")
    parser.add_argument("--scenario-start", type=float, default=60.0,
                        help="seconds into the replay when the first scenario starts; "
                             f"the next ones follow every {scenarios.SPACING} s (default 60)")
    parser.add_argument("--outage-minutes", type=float, default=scenarios.OUTAGE_SECONDS / 60,
                        help="length of payment_outage in replay minutes (default 10)")
    parser.add_argument("--scenario-log", help="where to write the scenario ground truth (JSON); "
                                               f"default next to --out, or {SCENARIO_LOG_DIR}/")
    parser.add_argument("--out", help="write events to this JSON Lines file instead of Kafka, "
                                      "as fast as possible on a simulated clock")
    parser.add_argument("--replay-start", type=utc_time,
                        help="event_time of the first event with --out (default: now)")
    parser.add_argument("--limit", type=int, help="stop after N events")

    args = parser.parse_args(argv)
    if args.end <= args.start:
        parser.error("--end must be after --start")
    if (args.speed or args.rate or 0) <= 0:
        parser.error("--speed / --rate must be > 0")
    if not 0 < args.sample_rate <= 1:
        parser.error("--sample-rate must be in (0, 1]")
    if not 0 <= args.late_rate < 1:
        parser.error("--late-rate must be in [0, 1)")
    if args.late_delay <= 0:
        parser.error("--late-delay must be > 0")
    if args.outage_minutes <= 0:
        parser.error("--outage-minutes must be > 0")
    if args.replay_start and not args.out:
        parser.error("--replay-start only works with --out; live replays start now")
    return args


def kafka_config() -> dict:
    load_dotenv()
    config = {
        "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
        "security.protocol": os.environ.get("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
        # keeps per-partition order and avoids duplicates when the client retries
        "enable.idempotence": True,
        # small local queue: when the broker can't keep up, produce() blocks soon, so the
        # measured rate is what the broker accepts, not what fits in memory
        "queue.buffering.max.messages": QUEUE_MAX_MESSAGES,
    }
    # optional batching knobs for throughput experiments; unset = client defaults
    for env, key in (("KAFKA_LINGER_MS", "linger.ms"), ("KAFKA_BATCH_SIZE", "batch.size")):
        if os.environ.get(env):
            config[key] = int(os.environ[env])
    if config["security.protocol"] == "SASL_SSL":  # Event Hubs
        config.update({
            "sasl.mechanism": "PLAIN",
            "sasl.username": "$ConnectionString",
            "sasl.password": os.environ["EVENTHUBS_CONNECTION_STRING"],
        })
    return config


def day_ranges(start: datetime, end: datetime):
    """Split [start, end) at midnight so each reader query covers at most one day."""
    cur = start
    while cur < end:
        next_midnight = datetime.combine(cur.date() + timedelta(days=1), datetime.min.time())
        nxt = min(next_midnight, end)
        yield cur, nxt
        cur = nxt


def iter_rows(args):
    """Raw rows of the whole range, in order, after user sampling."""
    for a, b in day_ranges(args.start, args.end):
        for row in reader.read_events(DATA, to_raw(a), to_raw(b)):
            if args.sample_rate < 1.0 and enrich._unit("sample", row["user_id"]) >= args.sample_rate:
                continue
            yield row


def real_timeline(args, original_start):
    """(due, row, None) for the dataset rows; due = seconds after the replay start."""
    for k, row in enumerate(iter_rows(args)):
        if args.speed:
            original = timeshift.parse_raw(row["event_time"])
            due = (original - original_start).total_seconds() / args.speed
        else:
            due = k / args.rate
        yield due, row, None


def late_delay(event_id: str, late_rate: float, max_delay: float) -> float:
    """Seconds to hold an event back, 0 for on-time events.

    Picked from the event_id hash, so the same events are late on every replay.
    """
    if late_rate <= 0 or enrich._unit("late", event_id) >= late_rate:
        return 0.0
    return max_delay * (LATE_MIN_SHARE + (1 - LATE_MIN_SHARE) * enrich._unit("late_delay", event_id))


def scenario_log_path(args, replay_start: datetime) -> Path:
    if args.scenario_log:
        return Path(args.scenario_log)
    if args.out:
        return Path(args.out).with_suffix(".scenarios.json")
    return Path(SCENARIO_LOG_DIR) / f"scenarios-{replay_start:%Y%m%dT%H%M%SZ}.json"


def write_scenario_log(path: Path, args, plan, replay_start: datetime, dropped: int):
    """Ground truth for evaluating the rules: one entry per scenario, times on the event_time axis."""
    def at(due):
        return timeshift.to_iso_ms(replay_start + timedelta(seconds=due))

    entries = []
    for entry in plan.log:
        entry = dict(entry)
        start, end = entry.pop("start_due"), entry.pop("end_due")
        entry.update(start=at(start), end=at(end))
        if entry["scenario"] == "payment_outage":
            entry["dropped_purchases"] = dropped
        entries.append(entry)
    log = {
        "replay_start": timeshift.to_iso_ms(replay_start),
        "dataset_range": [args.start.isoformat(), args.end.isoformat()],
        "speed": args.speed,
        "rate": args.rate,
        "sample_rate": args.sample_rate,
        "scenarios": entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
    print(f"scenario log: {path}")


def run(args):
    to_file = bool(args.out)
    provinces = enrich.load_provinces(PROVINCES)
    original_start = args.start.replace(tzinfo=UTC)

    if to_file:   # simulated clock: no waiting, sent_time follows the schedule
        replay_start = args.replay_start or datetime.now(UTC)
        clock = [0.0]

        def now():
            return clock[0]

        def sleep(seconds):
            clock[0] += seconds

        def sent_time():
            return replay_start + timedelta(seconds=clock[0])
    else:         # live replay: events happen "now"
        replay_start = datetime.now(UTC)
        now, sleep = time.monotonic, time.sleep

        def sent_time():
            return datetime.now(UTC)

    def original_at(due):
        return to_raw(original_start + timedelta(seconds=due * (args.speed or 1)))

    plan = scenarios.Plan()
    if args.scenarios:
        plan = scenarios.build(args.scenarios, args.scenario_start, original_at,
                               scenarios.load_ref_prices(PRICE_LIST), args.outage_minutes * 60)
    injected = ((inj.due, inj.row, inj.overrides) for inj in plan.injections)
    timeline = heapq.merge(real_timeline(args, original_start), injected, key=lambda t: t[0])

    wall_start = time.monotonic()
    clock_start = now()
    failed = 0
    delivered = 0   # acknowledged by the broker (or written to the file)
    sent = 0        # handed to the client
    late = 0
    fraud = 0
    dropped = 0
    lag = 0.0
    held = []   # late events waiting to go out: (release time, order, event)

    if to_file:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        out = open(args.out, "w", encoding="utf-8")  # noqa: SIM115 - closed in the finally block
        producer = None
    else:
        out = None
        producer = Producer(kafka_config())
        topic = os.environ.get("KAFKA_TOPIC", "events")

    def on_delivery(err, msg):
        nonlocal failed, delivered
        if err is None:
            delivered += 1
            return
        failed += 1
        if failed <= 5:
            print("delivery failed:", err)

    def send(event):
        nonlocal sent, delivered
        event["sent_time"] = timeshift.to_iso_ms(sent_time())
        if out is not None:
            out.write(json.dumps(event) + "\n")
            delivered += 1
        else:
            while True:
                try:
                    producer.produce(topic, key=str(event["user_id"]), value=json.dumps(event),
                                     on_delivery=on_delivery)
                    break
                except BufferError:   # local queue full: let the client send, then retry
                    producer.poll(0.5)
            producer.poll(0)
        sent += 1
        if sent % LOG_EVERY == 0:
            elapsed = time.monotonic() - wall_start
            print(f"{sent:,} sent | {sent / elapsed:,.0f} ev/s | behind schedule {lag:.2f}s "
                  f"| {len(held)} late held")

    def wait_until(target):
        """Sleep until `target` (on `now`'s clock), sending held late events as they come due."""
        while True:
            current = now()
            while held and held[0][0] <= current:
                send(heapq.heappop(held)[2])
            if current >= target:
                return
            next_release = held[0][0] if held else target
            sleep(min(target, next_release) - current)

    outage = plan.outage
    try:
        for i, (due, row, overrides) in enumerate(timeline):
            lag = max(0.0, now() - clock_start - due)   # > 0 when we fall behind schedule
            wait_until(clock_start + due)

            event = enrich.enrich(row, provinces,
                                  event_time=timeshift.to_iso_ms(replay_start + timedelta(seconds=due)))
            if overrides:
                event.update(overrides)
                fraud += 1
            elif (outage and outage[0] <= due < outage[1] and event["event_type"] == "purchase"
                  and event["payment_method"] == outage[2]):
                dropped += 1   # payment_outage: real purchases through this method vanish
                continue

            delay = late_delay(event["event_id"], args.late_rate, args.late_delay)
            if delay:
                event["is_late"] = True
                late += 1
                heapq.heappush(held, (now() + delay, i, event))
            else:
                send(event)

            if args.limit and i + 1 >= args.limit:
                break

        if held:   # the replay is over: still send the late events at their time
            wait_until(max(t for t, _, _ in held))
    except KeyboardInterrupt:
        print("stopped by user")
    finally:
        for _, _, event in sorted(held, key=lambda h: h[:2]):   # stopped early: send what is left
            send(event)
        remaining = 0
        if out is not None:
            out.close()
        else:
            try:
                remaining = producer.flush(30)
            except KeyboardInterrupt:   # Ctrl+C while flushing: report what is still queued
                remaining = len(producer)
        if args.scenarios:
            write_scenario_log(scenario_log_path(args, replay_start), args, plan, replay_start, dropped)
        elapsed = time.monotonic() - wall_start
        extra = f", {fraud:,} fraud, {dropped:,} dropped by outage" if args.scenarios else ""
        print(f"done: {sent:,} sent ({late:,} late), {delivered:,} delivered in {elapsed:,.1f}s "
              f"({delivered / max(elapsed, 1e-9):,.0f} ev/s), {failed} failed, {remaining} not delivered"
              f"{extra}")


if __name__ == "__main__":
    run(parse_args())
