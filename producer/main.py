"""Replay REES46 events into Kafka / Event Hubs.

Run from the repo root, for example:
    python producer/main.py --start 2019-11-01T09:00 --end 2019-11-01T10:00 --speed 4
    python producer/main.py --start 2019-11-01T09:00 --end 2019-11-01T10:00 --rate 500
Kafka settings come from .env (see .env.example).
"""
import argparse
import json
import os
import time
from datetime import UTC, datetime, timedelta

import enrich
import reader
import timeshift
from confluent_kafka import Producer
from dotenv import load_dotenv

DATA = "data/processed/2019-Nov.parquet"
PROVINCES = "stream/reference/provinces.csv"
LOG_EVERY = 10_000


def to_raw(dt: datetime) -> str:
    """datetime -> '2019-11-01 09:00:00 UTC', the format reader.read_events expects."""
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def parse_args():
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
    parser.add_argument("--limit", type=int, help="stop after N events")

    args = parser.parse_args()
    if args.end <= args.start:
        parser.error("--end must be after --start")
    if (args.speed or args.rate or 0) <= 0:
        parser.error("--speed / --rate must be > 0")
    if not 0 < args.sample_rate <= 1:
        parser.error("--sample-rate must be in (0, 1]")
    return args


def kafka_config() -> dict:
    load_dotenv()
    config = {
        "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
        "security.protocol": os.environ.get("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
        # keeps per-partition order and avoids duplicates when the client retries
        "enable.idempotence": True,
    }
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


def run(args):
    producer = Producer(kafka_config())
    topic = os.environ.get("KAFKA_TOPIC", "events")
    provinces = enrich.load_provinces(PROVINCES)

    original_start = args.start.replace(tzinfo=UTC)
    replay_start = datetime.now(UTC)   # live replay: events happen "now"
    clock_start = time.monotonic()
    failed = 0
    sent = 0
    lag = 0.0

    def on_delivery(err, msg):
        nonlocal failed
        if err is not None:
            failed += 1
            if failed <= 5:
                print("delivery failed:", err)

    try:
        for row in iter_rows(args):
            # seconds after replay_start at which this event is due
            if args.speed:
                original = timeshift.parse_raw(row["event_time"])
                due = (original - original_start).total_seconds() / args.speed
            else:
                due = sent / args.rate

            wait = due - (time.monotonic() - clock_start)
            if wait > 0:
                time.sleep(wait)
            lag = max(0.0, -wait)   # > 0 when we fall behind schedule

            event = enrich.enrich(
                row, provinces,
                event_time=timeshift.to_iso_ms(replay_start + timedelta(seconds=due)),
                sent_time=timeshift.to_iso_ms(datetime.now(UTC)),
            )
            while True:
                try:
                    producer.produce(topic, key=str(row["user_id"]), value=json.dumps(event),
                                     on_delivery=on_delivery)
                    break
                except BufferError:   # local queue full: let the client send, then retry
                    producer.poll(0.5)
            producer.poll(0)

            sent += 1
            if sent % LOG_EVERY == 0:
                elapsed = time.monotonic() - clock_start
                print(f"{sent:,} sent | {sent / elapsed:,.0f} ev/s | behind schedule {lag:.2f}s")
            if args.limit and sent >= args.limit:
                break
    except KeyboardInterrupt:
        print("stopped by user")
    finally:
        remaining = producer.flush(30)
        elapsed = time.monotonic() - clock_start
        print(f"done: {sent:,} sent in {elapsed:,.1f}s ({sent / max(elapsed, 1e-9):,.0f} ev/s), "
              f"{failed} failed, {remaining} not delivered")


if __name__ == "__main__":
    run(parse_args())