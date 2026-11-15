-- Run in sqldb-megasale-dev after Terraform has enabled the ASA system identity.
-- Execute as the SQL Entra administrator or another principal allowed to
-- create contained users and grant object permissions.

IF NOT EXISTS (
    SELECT 1
    FROM sys.database_principals
    WHERE name = N'asa-megasale-dev'
)
BEGIN
    CREATE USER [asa-megasale-dev] FROM EXTERNAL PROVIDER;
END;
GO

GRANT CONNECT TO [asa-megasale-dev];
GRANT SELECT, INSERT ON OBJECT::dbo.kpi_1min TO [asa-megasale-dev];
GRANT SELECT, INSERT ON OBJECT::dbo.pipeline_latency TO [asa-megasale-dev];
GO
