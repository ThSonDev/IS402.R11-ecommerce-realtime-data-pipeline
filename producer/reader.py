import duckdb

BATCH_SIZE = 10_000

COLUMNS = "event_time, event_type, product_id, category_code, brand, price, user_id, user_session"

def read_events(parquet_path: str, start: str, end: str):
    query = f"""
        SELECT DISTINCT {COLUMNS} 
        FROM read_parquet('{parquet_path}')
        WHERE event_time >= (?) 
        AND event_time < (?)
        ORDER BY event_time, event_type, product_id, category_code, brand, price, user_id, user_session
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