-- Run after 10_external.sql in the same serverless SQL database.
-- The raw view keeps one row per file record and exposes the date/hour
-- directory levels so Synapse can prune files when callers filter partitions.
CREATE OR ALTER VIEW [silver].[events_raw]
AS
SELECT
    TRY_CONVERT(int, src.schema_version) AS schema_version,
    TRY_CONVERT(varchar(36), src.event_id) AS event_id,
    NULLIF(LTRIM(RTRIM(TRY_CONVERT(varchar(32), src.event_type))), '') AS event_type,
    TRY_CONVERT(datetime2(3), src.event_time) AS event_time,
    TRY_CONVERT(datetime2(3), src.original_time, 127) AS original_time,
    TRY_CONVERT(datetime2(3), src.sent_time, 127) AS sent_time,
    TRY_CONVERT(bigint, src.user_id) AS user_id,
    TRY_CONVERT(varchar(64), src.session_id) AS session_id,
    TRY_CONVERT(varchar(64), src.order_id) AS order_id,
    TRY_CONVERT(varchar(64), src.device_id) AS device_id,
    TRY_CONVERT(bit, src.is_new_account) AS is_new_account,
    TRY_CONVERT(bigint, src.product_id) AS product_id,
    TRY_CONVERT(varchar(256), src.category_code) AS category_code,
    TRY_CONVERT(varchar(128), src.brand) AS brand,
    TRY_CONVERT(bigint, src.price_vnd) AS price_vnd,
    TRY_CONVERT(varchar(16), src.channel) AS channel,
    TRY_CONVERT(varchar(8), src.province_code) AS province_code,
    TRY_CONVERT(varchar(32), src.payment_method) AS payment_method,
    TRY_CONVERT(varchar(128), src.voucher_code) AS voucher_code,
    TRY_CONVERT(bit, src.is_fraud) AS is_fraud,
    TRY_CONVERT(varchar(32), src.scenario) AS scenario,
    TRY_CONVERT(bit, src.is_late) AS is_late,
    TRY_CONVERT(datetime2(3), src.EventEnqueuedUtcTime) AS EventEnqueuedUtcTime,
    TRY_CONVERT(smallint, src.filepath(1)) AS partition_year,
    TRY_CONVERT(tinyint, src.filepath(2)) AS partition_month,
    TRY_CONVERT(tinyint, src.filepath(3)) AS partition_day,
    TRY_CONVERT(tinyint, src.filepath(4)) AS partition_hour
FROM OPENROWSET(
    BULK 'raw_archive/*/*/*/*/*.parquet',
    DATA_SOURCE = 'MegasaleLake',
    FORMAT = 'PARQUET'
) AS src;
GO

-- Keep the latest enqueued copy of each event. Invalid IDs/timestamps are
-- excluded from the cleaned view; they remain inspectable in events_raw.
CREATE OR ALTER VIEW [silver].[events]
AS
WITH ranked AS
(
    SELECT
        *,
        ROW_NUMBER() OVER
        (
            PARTITION BY event_id
            ORDER BY EventEnqueuedUtcTime DESC, sent_time DESC
        ) AS duplicate_rank
    FROM [silver].[events_raw]
    WHERE event_id IS NOT NULL
      AND event_time IS NOT NULL
)
SELECT
    schema_version,
    event_id,
    event_type,
    event_time,
    original_time,
    sent_time,
    user_id,
    session_id,
    order_id,
    device_id,
    is_new_account,
    product_id,
    category_code,
    brand,
    price_vnd,
    channel,
    province_code,
    payment_method,
    voucher_code,
    is_fraud,
    scenario,
    is_late,
    EventEnqueuedUtcTime,
    partition_year,
    partition_month,
    partition_day,
    partition_hour
FROM ranked
WHERE duplicate_rank = 1;
GO
