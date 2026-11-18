"""Compare DuckDB reads of the same event rows in CSV.GZ, JSON.GZ, and Parquet."""

from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import time
from pathlib import Path

import duckdb


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def quote_identifier(value: str | None) -> str:
    if value is None:
        raise ValueError("Cannot quote a missing column")
    return '"' + value.replace('"', '""') + '"'


def input_files(pattern: str) -> list[str]:
    path = Path(pattern)
    if path.is_dir():
        pattern = str(path / "**" / "*.parquet")
    files = sorted(glob.glob(pattern, recursive=True))
    if not files:
        raise FileNotFoundError(f"No Parquet files matched: {pattern}")
    return files


def bytes_on_disk(paths: list[Path]) -> int:
    return sum(path.stat().st_size for path in paths)


def measure_query(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    runs: int,
    columns: dict[str, str],
) -> dict:
    identity = columns.get("event_id") or columns.get("user_session") or columns.get("session_id")
    value = columns.get("price_vnd") or columns.get("price")
    event_type = columns.get("event_type")
    late = columns.get("is_late")
    identity_expr = f"COUNT(DISTINCT {quote_identifier(identity)})" if identity else "CAST(NULL AS BIGINT)"
    purchase_expr = (
        f"SUM(CASE WHEN {quote_identifier(event_type)} = 'purchase' THEN 1 ELSE 0 END)"
        if event_type
        else "CAST(NULL AS BIGINT)"
    )
    value_expr = (
        f"CAST(ROUND(COALESCE(SUM(CASE WHEN {quote_identifier(event_type)} = 'purchase' "
        f"THEN {quote_identifier(value)} ELSE 0 END), 0), 2) AS DECIMAL(38, 2))"
        "::VARCHAR"
        if value and event_type
        else "CAST(NULL AS VARCHAR)"
    )
    late_expr = (
        f"SUM(CASE WHEN {quote_identifier(late)} THEN 1 ELSE 0 END)"
        if late
        else "CAST(NULL AS BIGINT)"
    )
    query = f"""
        SELECT
            COUNT(*) AS row_count,
            {identity_expr} AS distinct_identity_count,
            {purchase_expr} AS purchase_count,
            {value_expr} AS purchase_value_sum,
            {late_expr} AS late_events
        FROM {relation}
    """
    expected = tuple(connection.execute(query).fetchone())
    durations = []
    for _ in range(runs):
        started = time.perf_counter()
        actual = tuple(connection.execute(query).fetchone())
        durations.append(time.perf_counter() - started)
        if actual != expected:
            raise ValueError(f"Different aggregate for {relation}: {actual} != {expected}")
    return {
        "row_count": expected[0],
        "distinct_identity_count": expected[1],
        "purchase_count": expected[2],
        "purchase_value_sum": expected[3],
        "late_events": expected[4],
        "query_seconds_median": statistics.median(durations),
        "query_seconds_min": min(durations),
        "query_runs": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Parquet file glob or directory")
    parser.add_argument("--output", required=True, type=Path, help="Directory for temporary comparison files")
    parser.add_argument("--runs", type=int, default=5, help="Measured aggregate-query repetitions")
    parser.add_argument("--threads", type=int, default=4, help="DuckDB threads used for every format")
    parser.add_argument("--reuse", action="store_true", help="Reuse generated format files in the output directory")
    args = parser.parse_args()
    if args.runs < 1 or args.threads < 1:
        parser.error("--runs and --threads must be positive")

    files = input_files(args.input)
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve()
    csv_path = output / "events.csv.gz"
    json_path = output / "events.json.gz"
    parquet_path = output / "events_zstd.parquet"

    connection = duckdb.connect()
    connection.execute(f"SET threads = {args.threads}")
    quoted_files = ", ".join(sql_string(str(Path(name).resolve()).replace("\\", "/")) for name in files)
    connection.execute(
        f"CREATE VIEW source_events AS SELECT * FROM read_parquet([{quoted_files}], union_by_name=true)"
    )
    columns = {
        row[0].lower(): row[0]
        for row in connection.execute("DESCRIBE SELECT * FROM source_events").fetchall()
    }

    if args.reuse:
        missing = [str(path) for path in (csv_path, json_path, parquet_path) if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Missing generated formats for --reuse: {', '.join(missing)}")
    else:
        connection.execute(
            f"COPY (SELECT * FROM source_events) TO {sql_string(str(csv_path).replace('\\', '/'))} "
            "(HEADER, COMPRESSION GZIP)"
        )
        connection.execute(
            f"COPY (SELECT * FROM source_events) TO {sql_string(str(json_path).replace('\\', '/'))} "
            "(FORMAT JSON, ARRAY false, COMPRESSION GZIP)"
        )
        connection.execute(
            f"COPY (SELECT * FROM source_events) TO {sql_string(str(parquet_path).replace('\\', '/'))} "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )

    relations = {
        "input_parquet_files": "source_events",
        "csv_gzip": f"read_csv_auto({sql_string(str(csv_path).replace('\\', '/'))}, header=true)",
        "json_gzip": f"read_json_auto({sql_string(str(json_path).replace('\\', '/'))}, format='newline_delimited')",
        "parquet_zstd": f"read_parquet({sql_string(str(parquet_path).replace('\\', '/'))})",
    }
    sizes = {
        "input_parquet_files": bytes_on_disk([Path(name) for name in files]),
        "csv_gzip": csv_path.stat().st_size,
        "json_gzip": json_path.stat().st_size,
        "parquet_zstd": parquet_path.stat().st_size,
    }

    results = {
        "duckdb_version": duckdb.__version__,
        "source_file_count": len(files),
        "threads": args.threads,
        "reuse_generated_files": args.reuse,
        "source_pattern": args.input,
        "identity_column": columns.get("event_id") or columns.get("user_session") or columns.get("session_id"),
        "purchase_value_column": columns.get("price_vnd") or columns.get("price"),
        "formats": {},
    }
    baseline = None
    for name, relation in relations.items():
        metrics = measure_query(connection, relation, args.runs, columns)
        if baseline is None:
            baseline = {
                key: metrics[key]
                for key in (
                    "row_count",
                    "distinct_identity_count",
                    "purchase_count",
                    "purchase_value_sum",
                    "late_events",
                )
            }
        elif any(metrics[key] != value for key, value in baseline.items()):
            raise ValueError(f"Aggregate mismatch for {name}: {metrics} != {baseline}")
        results["formats"][name] = {
            "bytes": sizes[name],
            "mib": round(sizes[name] / (1024 * 1024), 3),
            **metrics,
        }

    results["machine"] = {
        "platform": os.name,
        "processor": os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
    }
    results_path = output / "results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"Results saved to {results_path}")


if __name__ == "__main__":
    main()
