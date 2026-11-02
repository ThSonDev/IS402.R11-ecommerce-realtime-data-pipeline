"""Read raw REES46 events for a time range: deduplicated and in a stable order."""
import duckdb

BATCH_SIZE = 10_000

COLUMNS = "event_time, event_type, product_id, category_code, brand, price, user_id, user_session"

# view -> cart -> purchase (sorting event_type alphabetically would put view last).
FUNNEL_RANK = "CASE event_type WHEN 'view' THEN 0 WHEN 'cart' THEN 1 ELSE 2 END"


def read_events(parquet_path: str, start: str, end: str):
    """Yield events with start <= event_time < end as dicts, one at a time.

    start / end are strings like '2019-11-01 00:00:00 UTC'.
    """
    query = f"""
        SELECT * FROM (
            SELECT DISTINCT {COLUMNS}
            FROM read_parquet('{parquet_path}')
            WHERE event_time >= ?
            AND event_time < ?
        )
        ORDER BY event_time, {FUNNEL_RANK}, {COLUMNS}
    """

    con = duckdb.connect()

    try:
        cur = con.execute(query, [start, end])
        names = [col[0] for col in cur.description]

        while True:
            rows = cur.fetchmany(BATCH_SIZE)
            if not rows:
                break
            for row in rows:
                yield dict(zip(names, row))

    finally:
        con.close()
