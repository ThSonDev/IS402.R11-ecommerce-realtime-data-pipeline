"""Read throughput from Kafka / Event Hubs: how fast one consumer drains the `events` topic.

Each run joins a new consumer group and reads from the oldest retained event, so it measures
reading what is already there (produce first, e.g. with scripts/bench_producer.py). Run from
the repo root:
    python scripts/bench_consumer.py                 # target from .env, like the producer
    python scripts/bench_consumer.py --limit 300000 --repeat 3
On Event Hubs the producer's send-only key cannot read: set EVENTHUBS_LISTEN_CONNECTION_STRING
to the `asa-listen` key (see producer/README.md).
"""
import argparse
import os
import statistics
import time
import uuid

from confluent_kafka import Consumer
from dotenv import load_dotenv


def consumer_config() -> dict:
    load_dotenv()
    config = {
        "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
        "security.protocol": os.environ.get("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
        "group.id": f"bench-{uuid.uuid4().hex[:8]}",   # new group: no committed offsets
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    }
    if config["security.protocol"] == "SASL_SSL":  # Event Hubs
        config.update({
            "sasl.mechanism": "PLAIN",
            "sasl.username": "$ConnectionString",
            "sasl.password": os.environ.get("EVENTHUBS_LISTEN_CONNECTION_STRING")
            or os.environ["EVENTHUBS_CONNECTION_STRING"],
        })
    return config


def read_once(topic: str, limit: int, idle: float) -> tuple[int, int, float]:
    """(messages, bytes, seconds), timed from the first message so joining the group is not counted."""
    consumer = Consumer(consumer_config())
    consumer.subscribe([topic])
    count = size = 0
    first = last = None
    waited_since = time.monotonic()
    try:
        while count < limit:
            batch = consumer.consume(num_messages=1000, timeout=1.0)
            now = time.monotonic()
            good = [m for m in batch if m.error() is None]
            if not good:
                if now - (last or waited_since) > idle:
                    break   # topic drained (or nothing arrives)
                continue
            first = first or now
            last = now
            count += len(good)
            size += sum(len(m.value() or b"") for m in good)
    finally:
        consumer.close()
    return count, size, (last - first) if first else 0.0


def main():
    parser = argparse.ArgumentParser(description="Measure consumer read throughput.")
    parser.add_argument("--limit", type=int, default=300_000, help="messages per run (default 300,000)")
    parser.add_argument("--repeat", type=int, default=3, help="runs (default 3)")
    parser.add_argument("--idle", type=float, default=10, help="stop after this many seconds without data")
    args = parser.parse_args()

    load_dotenv()
    topic = os.environ.get("KAFKA_TOPIC", "events")
    print(f"target: {os.environ['KAFKA_BOOTSTRAP_SERVERS']} | topic {topic} | {args.repeat} runs")
    rates = []
    for run in range(1, args.repeat + 1):
        count, size, seconds = read_once(topic, args.limit, args.idle)
        rate = count / seconds if seconds else 0.0
        rates.append(rate)
        print(f"run {run}: {count:,} messages, {size / 1e6:,.1f} MB in {seconds:.2f} s "
              f"({rate:,.0f} ev/s, {size / 1e6 / max(seconds, 1e-9):,.1f} MB/s)")
    print(f"median: {statistics.median(rates):,.0f} ev/s")


if __name__ == "__main__":
    main()
