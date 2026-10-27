r"""Download one month of REES46 data into data/raw/ and convert it to Parquet in data/processed/.

Usage: .venv\Scripts\python scripts\prepare_data.py [2019-Nov]
# Linux: .venv/bin/python scripts/prepare_data.py [2019-Nov]
"""
import sys, time, urllib.request
from pathlib import Path

import duckdb

month = sys.argv[1] if len(sys.argv) > 1 else "2019-Nov"
raw = Path(f"data/raw/{month}.csv.gz")
out = Path(f"data/processed/{month}.parquet")
raw.parent.mkdir(parents=True, exist_ok=True)
out.parent.mkdir(parents=True, exist_ok=True)

if not raw.exists():
    url = f"https://data.rees46.com/datasets/marketplace/{month}.csv.gz"
    print(f"downloading {url} (~3 GB) ...")
    tmp = raw.with_suffix(".part")  # avoid leaving a truncated file under the final name
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(raw)

t = time.time()
# event_time stays a string ("2019-11-01 00:00:00 UTC"), parsing happens downstream.
duckdb.connect().execute(f"""
COPY (SELECT * FROM read_csv('{raw.as_posix()}', header=true, types={{'event_time': 'VARCHAR'}}))
TO '{out.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
""")
print(f"wrote {out} ({out.stat().st_size / 1e9:.2f} GB) in {time.time() - t:.0f}s")
