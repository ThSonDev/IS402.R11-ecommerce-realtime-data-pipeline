"""Measure the ack latency of sending events to one Kafka / Event Hubs bootstrap server (#66).

Sends --count small events at a fixed --rate and times each one from produce() to its delivery
callback. Run it once per region from the same machine and compare. From the repo root:
    python scripts/measure_send_latency.py --bootstrap evhns-x.servicebus.windows.net:9093
The Event Hubs connection string (Send policy of that namespace) is read from the environment
variable named by --conn-env (default EVENTHUBS_CONNECTION_STRING), never from the command line.
Without --bootstrap, KAFKA_BOOTSTRAP_SERVERS / KAFKA_SECURITY_PROTOCOL / KAFKA_TOPIC from .env.
Only the producer-to-broker ack is measured, not Stream Analytics.
"""
import argparse
import math
import os
import statistics
import time

from confluent_kafka import Producer
from dotenv import load_dotenv

PAYLOAD = b"x" * 600   # about one enriched event
WARMUP = 50             # first events also open the connection: reported apart, not in the percentiles


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (pct 0-100) of a non-empty list."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(pct / 100 * len(ordered)) - 1)]


def summarize(latencies: list[float], failed: int) -> dict:
    """Latencies in ms of acked events -> mean / p50 / p95 / p99 plus the failure count."""
    if not latencies:
        return {"acked": 0, "failed": failed}
    return {
        "acked": len(latencies), "failed": failed, "mean": statistics.mean(latencies),
        "p50": percentile(latencies, 50), "p95": percentile(latencies, 95), "p99": percentile(latencies, 99),
    }


def measure(config: dict, topic: str, count: int, rate: float) -> dict:
    latencies: list[float] = []   # in ack order, which is send order within a partition

    def on_delivery(err, _msg, sent_at):
        if err is None:   # failed and unacked events are counted as count - len(latencies)
            latencies.append((time.monotonic() - sent_at) * 1000)

    producer = Producer(config)
    start = time.monotonic()
    for i in range(count):
        wait = start + i / rate - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        sent_at = time.monotonic()
        producer.produce(topic, PAYLOAD, on_delivery=lambda e, m, t=sent_at: on_delivery(e, m, t))
        producer.poll(0)
    producer.flush(30)
    result = summarize(latencies[WARMUP:], count - len(latencies))
    result["warmup_max"] = max(latencies[:WARMUP], default=0.0)
    return result


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Measure producer-to-broker ack latency.")
    parser.add_argument("--bootstrap", default=os.environ.get("KAFKA_BOOTSTRAP_SERVERS"))
    parser.add_argument("--topic", default=os.environ.get("KAFKA_TOPIC", "events"))
    parser.add_argument("--count", type=int, default=2000)
    parser.add_argument("--rate", type=float, default=50, help="events per second (default 50)")
    parser.add_argument("--conn-env", default="EVENTHUBS_CONNECTION_STRING",
                        help="name of the env var holding the Event Hubs connection string")
    args = parser.parse_args()

    security = os.environ.get("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
    if args.bootstrap and args.bootstrap.endswith(".servicebus.windows.net:9093"):
        security = "SASL_SSL"
    config = {"bootstrap.servers": args.bootstrap, "security.protocol": security, "linger.ms": 0}
    if security == "SASL_SSL":
        config.update({"sasl.mechanism": "PLAIN", "sasl.username": "$ConnectionString",
                       "sasl.password": os.environ[args.conn_env]})
    result = measure(config, args.topic, args.count, args.rate)
    print(f"target: {args.bootstrap} | {args.count:,} events at {args.rate:g} ev/s")
    if result["acked"] == 0:
        raise SystemExit(f"no event acked, {result['failed']} failed")
    print(f"acked {result['acked']:,}, failed {result['failed']} | ack ms: mean {result['mean']:.1f}, "
          f"p50 {result['p50']:.1f}, p95 {result['p95']:.1f}, p99 {result['p99']:.1f} "
          f"(first {WARMUP} events left out, their max {result['warmup_max']:.1f})")


if __name__ == "__main__":
    main()
