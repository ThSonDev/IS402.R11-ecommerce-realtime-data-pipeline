"""Laptop side of the laptop-vs-cloud benchmark (rubric 1.3): one month aggregated with DuckDB.

The same aggregation runs on Synapse serverless with scripts/sql/bench_monthly_aggregate.sql,
so both sides do the same work on the same file. Run from the repo root:
    python scripts/bench_batch.py
    python scripts/bench_batch.py --repeat 5 --threads 4
"""
import argparse
import os
import platform
import statistics
import time

import duckdb

DATA = "data/processed/2019-Nov.parquet"

# Per day and event type: events, distinct users, purchase revenue (USD, as in the dataset).
QUERY = """
SELECT CAST(substr(event_time, 1, 10) AS DATE) AS day,
       event_type,
       count(*) AS events,
       count(DISTINCT user_id) AS users,
       sum(CASE WHEN event_type = 'purchase' THEN price END) AS revenue_usd
FROM read_parquet('{path}')
GROUP BY 1, 2
ORDER BY 1, 2
"""


def main():
    parser = argparse.ArgumentParser(description="Time the monthly aggregation with DuckDB.")
    parser.add_argument("--data", default=DATA)
    parser.add_argument("--repeat", type=int, default=3, help="measured runs after one warm-up (default 3)")
    parser.add_argument("--threads", type=int, help="DuckDB threads (default: all cores)")
    args = parser.parse_args()

    con = duckdb.connect()
    if args.threads:
        con.execute(f"SET threads = {args.threads}")
    threads = con.execute("SELECT current_setting('threads')").fetchone()[0]
    size_gb = os.path.getsize(args.data) / 1e9
    print(f"{platform.processor() or platform.machine()} | {os.cpu_count()} logical CPUs | "
          f"DuckDB {duckdb.__version__}, {threads} threads | {args.data} ({size_gb:.2f} GB)")

    sql = QUERY.format(path=args.data)
    times, rows = [], None
    for run in range(args.repeat + 1):
        start = time.perf_counter()
        rows = con.execute(sql).fetchall()
        seconds = time.perf_counter() - start
        label = "warm-up" if run == 0 else f"run {run}"
        print(f"{label}: {seconds:.2f} s")
        if run:
            times.append(seconds)

    events = sum(r[2] for r in rows)
    revenue = sum(r[4] or 0 for r in rows)
    print(f"result: {len(rows)} rows (day x event_type), {events:,} events, revenue {revenue:,.2f} USD")
    print(f"median of {args.repeat}: {statistics.median(times):.2f} s (min {min(times):.2f}, max {max(times):.2f})")


if __name__ == "__main__":
    main()
