-- Measurements for one test run (#86). Run with sqlcmd, times are UTC (alert_time / window_end):
--   sqlcmd -S sql-megasale-dev.database.windows.net -d sqldb-megasale-dev --authentication-method ActiveDirectoryAzCli -i scripts/sql/e2e_metrics.sql -v from="'2026-11-22 09:00'" to="'2026-11-22 10:00'"
-- Export alerts to CSV: add  -Q "SELECT ... FROM dbo.alerts WHERE ..." -s "," -W -o alerts.csv  (see docs/e2e-run.md).

-- Alerts per rule
SELECT rule_name, COUNT(*) AS alerts, COUNT(DISTINCT entity_id) AS entities
FROM dbo.alerts WHERE alert_time >= $(from) AND alert_time < $(to)
GROUP BY rule_name ORDER BY rule_name;

-- Pipeline latency per event-time minute: mean and p95 of the per-minute averages (ms)
SELECT COUNT(*) AS minutes, SUM(event_count) AS events,
       AVG(avg_producer_to_eventhub_ms) AS producer_to_eventhub_mean,
       AVG(avg_eventhub_to_asa_ms) AS eventhub_to_asa_mean,
       AVG(avg_end_to_end_ms) AS end_to_end_mean
FROM dbo.pipeline_latency WHERE window_end > $(from) AND window_end <= $(to);

SELECT DISTINCT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY avg_end_to_end_ms) OVER () AS end_to_end_p95
FROM dbo.pipeline_latency WHERE window_end > $(from) AND window_end <= $(to);
