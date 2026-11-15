-- Run in sqldb-megasale-dev before starting the Stream Analytics job.
-- Types and columns match section 3 of docs/event-schema.md.

IF OBJECT_ID(N'dbo.kpi_1min', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.kpi_1min (
        window_end     datetime2(3) NOT NULL,
        channel        nvarchar(32) NOT NULL,
        province_code  nvarchar(8) NOT NULL,
        view_count     bigint NOT NULL,
        cart_count     bigint NOT NULL,
        purchase_count bigint NOT NULL,
        order_count    bigint NOT NULL,
        gmv_vnd        bigint NOT NULL
    );
END;
GO

IF OBJECT_ID(N'dbo.pipeline_latency', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.pipeline_latency (
        window_end                 datetime2(3) NOT NULL,
        event_count                bigint NOT NULL,
        avg_producer_to_eventhub_ms float NOT NULL,
        avg_eventhub_to_asa_ms      float NOT NULL,
        avg_end_to_end_ms           float NOT NULL
    );
END;
GO
