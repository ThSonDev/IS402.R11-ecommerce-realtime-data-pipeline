"""Build the Stream Analytics reference price list from monthly REES46 data.

Usage: .venv\\Scripts\\python scripts\\create_price_list.py
"""
import argparse
import csv
from pathlib import Path

import duckdb

USD_VND = 25_850
DEFAULT_INPUT = Path("data/processed/2019-Nov.parquet")
DEFAULT_OUTPUT = Path("stream/reference/price_list.csv")


def build_price_list(input_path: Path, output_path: Path) -> int:
    if not input_path.is_file():
        raise FileNotFoundError(
            f"Processed dataset not found: {input_path}. "
            "Prepare it first using the instructions in data/README.md."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            """
            WITH deduplicated_events AS (
                SELECT DISTINCT
                    event_time,
                    event_type,
                    product_id,
                    category_code,
                    brand,
                    price,
                    user_id,
                    user_session
                FROM read_parquet(?)
            )
            SELECT
                product_id::BIGINT AS product_id,
                ROUND_EVEN(MEDIAN(ROUND_EVEN(price * ?, 0)), 0)::BIGINT AS list_price_vnd
            FROM deduplicated_events
            WHERE product_id IS NOT NULL
              AND price IS NOT NULL
              AND price > 0
            GROUP BY product_id
            ORDER BY product_id
            """,
            [str(input_path), USD_VND],
        ).fetchall()
    finally:
        connection.close()

    if not rows:
        raise ValueError(f"No products with a positive price found in {input_path}")

    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file, lineterminator="\n")
        writer.writerow(["product_id", "list_price_vnd"])
        writer.writerows(rows)

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    product_count = build_price_list(args.input, args.output)
    print(f"Wrote {product_count:,} products to {args.output}")
    print(f"Method: median positive event price for November, converted at {USD_VND:,} VND/USD.")


if __name__ == "__main__":
    main()
