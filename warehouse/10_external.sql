-- Run in the dedicated serverless SQL database (not in master).
-- Access to ADLS uses the caller's Microsoft Entra identity.
IF NOT EXISTS (
    SELECT 1
    FROM sys.external_data_sources
    WHERE name = N'MegasaleLake'
)
BEGIN
    CREATE EXTERNAL DATA SOURCE [MegasaleLake]
    WITH (LOCATION = N'https://stmegasaledev.dfs.core.windows.net/lake');
END;
GO

-- The province dimension is maintained as a versioned CSV in the reference
-- container (uploaded by infra/storage.tf). Synapse uses the caller's Entra
-- identity for both containers.
IF NOT EXISTS (
    SELECT 1
    FROM sys.external_data_sources
    WHERE name = N'MegasaleReference'
)
BEGIN
    CREATE EXTERNAL DATA SOURCE [MegasaleReference]
    WITH (LOCATION = N'https://stmegasaledev.dfs.core.windows.net/reference');
END;
GO

IF SCHEMA_ID(N'silver') IS NULL
BEGIN
    EXEC(N'CREATE SCHEMA [silver]');
END;
GO

IF SCHEMA_ID(N'gold') IS NULL
BEGIN
    EXEC(N'CREATE SCHEMA [gold]');
END;
GO
