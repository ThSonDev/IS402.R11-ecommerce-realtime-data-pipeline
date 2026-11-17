-- Run after 20_silver.sql in megasale_warehouse (serverless SQL only).
-- Natural keys keep the views usable without adding a stateful/dedicated pool.
CREATE OR ALTER VIEW [gold].[dim_date]
AS
SELECT DISTINCT
    CONVERT(int, YEAR(event_time) * 1000000 + MONTH(event_time) * 10000 + DAY(event_time) * 100 + DATEPART(hour, event_time)) AS date_key,
    CONVERT(date, event_time) AS calendar_date,
    YEAR(event_time) AS calendar_year,
    DATEPART(quarter, event_time) AS calendar_quarter,
    MONTH(event_time) AS calendar_month,
    DAY(event_time) AS day_of_month,
    DATENAME(weekday, event_time) AS day_name,
    DATEPART(weekday, event_time) AS day_of_week,
    DATEPART(hour, event_time) AS hour_utc
FROM [silver].[events]
WHERE event_time IS NOT NULL;
GO

CREATE OR ALTER VIEW [gold].[dim_product]
AS
WITH ranked AS
(
    SELECT
        product_id,
        category_code,
        brand,
        EventEnqueuedUtcTime,
        ROW_NUMBER() OVER
        (
            PARTITION BY product_id
            ORDER BY EventEnqueuedUtcTime DESC, event_time DESC, event_id DESC
        ) AS product_rank
    FROM [silver].[events]
    WHERE product_id IS NOT NULL
)
SELECT
    product_id,
    category_code,
    CASE
        WHEN category_code IS NULL THEN NULL
        WHEN CHARINDEX('.', category_code) = 0 THEN category_code
        ELSE LEFT(category_code, CHARINDEX('.', category_code) - 1)
    END AS category_level_1,
    CASE
        WHEN category_code IS NULL OR CHARINDEX('.', category_code) = 0 THEN NULL
        WHEN CHARINDEX('.', category_code, CHARINDEX('.', category_code) + 1) = 0
            THEN SUBSTRING(category_code, CHARINDEX('.', category_code) + 1, 256)
        ELSE SUBSTRING(
            category_code,
            CHARINDEX('.', category_code) + 1,
            CHARINDEX('.', category_code, CHARINDEX('.', category_code) + 1) - CHARINDEX('.', category_code) - 1
        )
    END AS category_level_2,
    CASE
        WHEN category_code IS NULL OR CHARINDEX('.', category_code, CHARINDEX('.', category_code) + 1) = 0 THEN NULL
        ELSE SUBSTRING(category_code, CHARINDEX('.', category_code, CHARINDEX('.', category_code) + 1) + 1, 256)
    END AS category_level_3,
    brand
FROM ranked
WHERE product_rank = 1;
GO

CREATE OR ALTER VIEW [gold].[dim_channel]
AS
SELECT DISTINCT
    channel AS channel_key,
    channel
FROM [silver].[events]
WHERE channel IS NOT NULL;
GO

CREATE OR ALTER VIEW [gold].[dim_province]
AS
SELECT
    TRY_CONVERT(varchar(8), src.province_code) AS province_key,
    TRY_CONVERT(varchar(8), src.province_code) AS province_code,
    TRY_CONVERT(varchar(128), src.province_name) AS province_name,
    TRY_CONVERT(varchar(16), src.region) AS region,
    TRY_CONVERT(bigint, src.population) AS population
FROM OPENROWSET(
    BULK 'provinces.csv',
    DATA_SOURCE = 'MegasaleReference',
    FORMAT = 'CSV',
    PARSER_VERSION = '2.0',
    HEADER_ROW = TRUE
) WITH
(
    province_code varchar(8) COLLATE Latin1_General_100_BIN2_UTF8,
    province_name varchar(128) COLLATE Latin1_General_100_BIN2_UTF8,
    region varchar(16) COLLATE Latin1_General_100_BIN2_UTF8,
    population bigint
) AS src;
GO

CREATE OR ALTER VIEW [gold].[dim_payment]
AS
SELECT DISTINCT
    COALESCE(payment_method, '(unknown)') AS payment_key,
    COALESCE(payment_method, '(unknown)') AS payment_method
FROM [silver].[events]
WHERE event_type = 'purchase';
GO

CREATE OR ALTER VIEW [gold].[fact_events]
AS
SELECT
    e.event_id,
    CONVERT(int, YEAR(e.event_time) * 1000000 + MONTH(e.event_time) * 10000 + DAY(e.event_time) * 100 + DATEPART(hour, e.event_time)) AS date_key,
    e.product_id AS product_key,
    e.channel AS channel_key,
    e.province_code AS province_key,
    CASE
        WHEN e.event_type = 'purchase' THEN COALESCE(e.payment_method, '(unknown)')
        ELSE NULL
    END AS payment_key,
    e.event_time,
    e.event_type,
    e.user_id,
    e.session_id,
    e.order_id,
    e.price_vnd,
    e.is_fraud,
    e.is_late,
    e.scenario,
    e.partition_year,
    e.partition_month,
    e.partition_day,
    e.partition_hour
FROM [silver].[events] AS e;
GO

-- Deliberately not defining gold.fact_alerts yet. The current alerts output is
-- written to Azure SQL DB, not to this lake; serverless SQL cannot read that
-- table through MegasaleLake. Add the view when an alerts parquet source exists.
