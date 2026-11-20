"""Measure producer throughput at several --rate levels and print a table.

Each level runs producer/main.py for --duration seconds (stopped like Ctrl+C if it is still
going), --repeat times. Run from the repo root, on Linux / WSL (runs are stopped with SIGINT):
    python scripts/bench_producer.py
    python scripts/bench_producer.py --rates 500,1000,1500,2000,100000 --duration 60 --repeat 3
The target (local Kafka or Event Hubs) comes from .env, as for the producer; variables already
set in the environment win, e.g. KAFKA_LINGER_MS=50 python scripts/bench_producer.py ...
The rate reported is what the broker acknowledged, not what the client queued.
"""
import argparse
import os
import re
import signal
import statistics
import subprocess
import sys
import time

from dotenv import dotenv_values

DONE = re.compile(
    r"done: ([\d,]+) sent \(([\d,]+) late\), ([\d,]+) delivered in ([\d,.]+)s \(([\d,]+) ev/s\), "
    r"(\d+) failed, (\d+) not delivered"
)
BEHIND = re.compile(r"behind schedule ([\d.]+)s")
# extra seconds before stopping a run: runs that keep up end on --limit and still have time
# to flush the (at most 10,000 message) client queue
GRACE = 15


def num(text: str) -> float:
    return float(text.replace(",", ""))


def run_once(rate: float, args) -> dict:
    """Run the producer once at `rate` and parse its summary line."""
    cmd = [sys.executable, "producer/main.py", "--start", args.start, "--end", args.end,
           "--rate", str(rate), "--limit", str(int(rate * args.duration))]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        out, _ = proc.communicate(timeout=args.duration + GRACE)
    except subprocess.TimeoutExpired:
        proc.send_signal(signal.SIGINT)   # main.py flushes and still prints its summary
        out, _ = proc.communicate()
    done = DONE.search(out)
    if done is None:
        sys.exit(f"no summary from the producer at --rate {rate}:\n{out[-2000:]}")
    behind = BEHIND.findall(out)
    return {
        "sent": int(num(done[1])),
        "delivered": int(num(done[3])),
        "evs": num(done[5]),
        "failed": int(done[6]),
        "undelivered": int(done[7]),
        "behind": float(behind[-1]) if behind else 0.0,
    }


def main():
    parser = argparse.ArgumentParser(description="Measure producer throughput at several --rate levels.")
    parser.add_argument("--rates", default="500,1000,1500,2000,100000",
                        help="comma-separated --rate levels; a very high one measures the ceiling")
    parser.add_argument("--duration", type=float, default=60, help="seconds per run (default 60)")
    parser.add_argument("--repeat", type=int, default=3, help="runs per level (default 3)")
    parser.add_argument("--pause", type=float, default=5, help="seconds between runs (default 5)")
    parser.add_argument("--start", default="2019-11-01T09:00")
    parser.add_argument("--end", default="2019-11-03T09:00",
                        help="long enough not to run out of events at the fastest level")
    args = parser.parse_args()
    rates = [float(r) for r in args.rates.split(",")]

    env = {**dotenv_values(".env"), **os.environ}   # same precedence as load_dotenv in main.py
    target = env.get("KAFKA_BOOTSTRAP_SERVERS", "?")
    batching = f"linger.ms={env.get('KAFKA_LINGER_MS') or 'default'}, batch.size={env.get('KAFKA_BATCH_SIZE') or 'default'}"
    total = len(rates) * args.repeat * (args.duration + GRACE + args.pause)
    print(f"target: {target} | {batching} | {len(rates)} levels x {args.repeat} runs | about {total / 60:.0f} min")

    rows = []
    for rate in rates:
        runs = []
        for i in range(args.repeat):
            r = run_once(rate, args)
            runs.append(r)
            print(f"rate {rate:,.0f} run {i + 1}: {r['delivered']:,} delivered, {r['evs']:,.0f} ev/s, "
                  f"behind {r['behind']:.1f}s, {r['failed']} failed, {r['undelivered']} not delivered")
            time.sleep(args.pause)
        evs = [r["evs"] for r in runs]
        rows.append((rate, statistics.mean(evs), min(evs), max(evs),
                     statistics.mean(r["behind"] for r in runs),
                     sum(r["failed"] for r in runs), sum(r["undelivered"] for r in runs)))

    print()
    print(f"| --rate | delivered ev/s (mean of {args.repeat}) | min–max | behind schedule (s) | failed | not delivered |")
    print("|---|---|---|---|---|---|")
    for rate, mean, lo, hi, behind, failed, undelivered in rows:
        print(f"| {rate:,.0f} | {mean:,.0f} | {lo:,.0f}–{hi:,.0f} | {behind:.1f} | {failed} | {undelivered} |")


if __name__ == "__main__":
    main()