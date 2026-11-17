-- Run against master on the serverless SQL endpoint.
-- Serverless SQL databases hold metadata only; this does not create a dedicated pool.
IF DB_ID(N'megasale_warehouse') IS NULL
BEGIN
    CREATE DATABASE [megasale_warehouse];
END;
GO
