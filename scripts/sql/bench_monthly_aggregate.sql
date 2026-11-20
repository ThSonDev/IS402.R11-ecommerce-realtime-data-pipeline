-- Cloud side of the laptop-vs-cloud benchmark (rubric 1.3); laptop side: scripts/bench_batch.py.
-- Same aggregation over the same file: data/processed/2019-Nov.parquet uploaded to
-- lake/benchmark/rees46/2019-Nov.parquet. Run in the serverless database that has the
-- MegasaleLake data source (warehouse/10_external.sql). Read the duration and "data processed"
-- of each run from Synapse Studio (Monitor -> SQL requests); run once to warm up, then 3 times.
SELECT CAST(LEFT(r.event_time, 10) AS date) AS day,
       r.event_type,
       COUNT_BIG(*) AS events,
       COUNT(DISTINCT r.user_id) AS users,
       SUM(CASE WHEN r.event_type = 'purchase' THEN r.price END) AS revenue_usd
FROM OPENROWSET(
    BULK 'benchmark/rees46/2019-Nov.parquet',
    DATA_SOURCE = 'MegasaleLake',
    FORMAT = 'PARQUET'
) AS r
GROUP BY CAST(LEFT(r.event_time, 10) AS date), r.event_type
ORDER BY day, r.event_type;
