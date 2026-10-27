r"""Basic EDA for one month of REES46 events.

Usage: .venv\Scripts\python analysis\eda.py [data/processed/2019-Nov.parquet]
# Linux: .venv/bin/python analysis/eda.py [data/processed/2019-Nov.parquet]
Prepare the Parquet first with scripts/prepare_data.py (see data/README.md).
"""
import sys, time, duckdb

sys.stdout.reconfigure(encoding="utf-8")
con = duckdb.connect()
t = time.time()

src = sys.argv[1] if len(sys.argv) > 1 else "data/processed/2019-Nov.parquet"
con.execute(f"""CREATE VIEW ev AS SELECT *, strptime(replace(event_time::VARCHAR,' UTC',''), '%Y-%m-%d %H:%M:%S') ts
FROM '{src}'""")

def q(title, sql):
    print(f"\n## {title}")
    print(con.sql(sql))

q("overview", """SELECT count(*) rows, count(DISTINCT user_id) users, count(DISTINCT user_session) sessions,
  count(DISTINCT product_id) products, count(DISTINCT brand) brands, count(DISTINCT category_code) cat_codes,
  min(ts) first_ts, max(ts) last_ts FROM ev""")
q("event types", "SELECT event_type, count(*) n, round(100*count(*)/sum(count(*)) OVER (),2) pct FROM ev GROUP BY 1 ORDER BY 2 DESC")
q("null / bad rates (%)", """SELECT round(100*avg((category_code IS NULL)::INT),2) cat_null, round(100*avg((brand IS NULL)::INT),2) brand_null,
  round(100*avg((user_session IS NULL)::INT),3) session_null, round(100*avg((price<=0)::INT),3) price_le0 FROM ev""")
q("exact duplicate rows", "SELECT count(*) - (SELECT count(*) FROM (SELECT DISTINCT * EXCLUDE ts FROM ev)) dup FROM ev")
q("price (purchase)", """SELECT round(min(price),2) min, round(quantile_cont(price,0.5),2) p50, round(avg(price),2) avg,
  round(quantile_cont(price,0.99),2) p99, round(max(price),2) max FROM ev WHERE event_type='purchase'""")
q("funnel (sessions)", """WITH s AS (SELECT user_session, max((event_type='view')::INT) v, max((event_type='cart')::INT) c,
  max((event_type='purchase')::INT) p FROM ev GROUP BY 1)
  SELECT sum(v) view_s, sum(c) cart_s, sum(p) purchase_s, round(100*sum(p)/sum(v),2) conv_pct FROM s""")
q("top level-1 categories by revenue", """SELECT split_part(coalesce(category_code,'(null)'),'.',1) cat, count(*) purchases,
  round(sum(price)/1e6,2) revenue_musd FROM ev WHERE event_type='purchase' GROUP BY 1 ORDER BY 3 DESC LIMIT 8""")
q("top brands by revenue", """SELECT brand, count(*) purchases, round(sum(price)/1e6,2) revenue_musd FROM ev
  WHERE event_type='purchase' GROUP BY 1 ORDER BY 3 DESC LIMIT 8""")
q("daily (look for sale peaks)", """SELECT ts::DATE d, count(*) events, sum((event_type='purchase')::INT) purchases,
  round(sum(CASE WHEN event_type='purchase' THEN price END)/1e3,0) revenue_kusd FROM ev GROUP BY 1 ORDER BY 1""")
q("hour of day UTC (purchases)", "SELECT hour(ts) h, count(*) n FROM ev WHERE event_type='purchase' GROUP BY 1 ORDER BY 1")
q("events per second (sizing Event Hubs: 1 TU = 1000 ev/s ingress)", """WITH s AS (SELECT ts, count(*) n FROM ev GROUP BY 1)
  SELECT round(avg(n),1) avg_eps, quantile_cont(n,0.99) p99_eps, max(n) max_eps FROM s""")
q("rule 1 baseline: max purchases by one user in a 1-min bucket", """WITH m AS (SELECT user_id, date_trunc('minute',ts) mi, count(*) n
  FROM ev WHERE event_type='purchase' GROUP BY 1,2)
  SELECT n purchases_in_1min, count(*) user_minutes FROM m GROUP BY 1 ORDER BY 1 DESC LIMIT 10""")
q("rule 3 baseline: price spread per product (max/min)", """WITH p AS (SELECT product_id, max(price)/nullif(min(price),0) r FROM ev
  WHERE price>0 GROUP BY 1) SELECT round(quantile_cont(r,0.5),2) p50, round(quantile_cont(r,0.95),2) p95,
  round(quantile_cont(r,0.99),2) p99, round(max(r),1) max FROM p""")
q("sample purchase rows", "SELECT * EXCLUDE ts FROM ev WHERE event_type='purchase' LIMIT 3")
print(f"\ntotal: {time.time()-t:.0f}s")
