# Stream Analytics job. Terraform creates it stopped: billed only while running,
# so start it for a test and stop it right after (see README).
# The query lives in stream/query.asaql (owned by Thắng); changing it updates the job,
# which only works while the job is stopped.
resource "azurerm_stream_analytics_job" "main" {
  name                = "asa-${local.name}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.main.name
  sku_name            = "StandardV2"
  streaming_units     = 3 # V2 API takes SU x 10: 3 = 1/3 SU (smallest), 7 = 2/3, 10 = 1
  compatibility_level = "1.2"
  data_locale         = "en-US"
  output_error_policy = "Stop"

  # Use a short late-arrival tolerance to keep one-minute outputs timely.
  # Adjust late and out-of-order events instead of dropping them; see stream/README.md.
  events_late_arrival_max_delay_in_seconds = 5
  events_out_of_order_max_delay_in_seconds = 0
  events_out_of_order_policy               = "Adjust"

  transformation_query = file("${path.module}/../stream/query.asaql")
  tags                 = local.tags

  # SQL Database and Power BI use the job identity; no SQL or refresh-token
  # credentials are stored in Terraform state.
  identity {
    type = "SystemAssigned"
  }
}

# Input alias `events` in the query. Destroyed together with the Event Hubs namespace
# (destroy-eventhubs) and recreated on the next apply.
resource "azurerm_stream_analytics_stream_input_eventhub_v2" "events" {
  name                         = "events"
  stream_analytics_job_id      = azurerm_stream_analytics_job.main.id
  servicebus_namespace         = azurerm_eventhub_namespace.main.name
  eventhub_name                = azurerm_eventhub.events.name
  eventhub_consumer_group_name = azurerm_eventhub_consumer_group.asa.name
  shared_access_policy_name    = azurerm_eventhub_authorization_rule.asa.name
  shared_access_policy_key     = azurerm_eventhub_authorization_rule.asa.primary_key

  serialization {
    type     = "Json"
    encoding = "UTF8"
  }
}

# Reference data aliases `price_list` and `provinces`, read from the `reference` container.
# Storage key auth: managed identity would need a role assignment the CI app can't create.
resource "azurerm_stream_analytics_reference_input_blob" "main" {
  for_each                  = azurerm_storage_blob.reference
  name                      = trimsuffix(each.key, ".csv")
  stream_analytics_job_name = azurerm_stream_analytics_job.main.name
  resource_group_name       = data.azurerm_resource_group.main.name
  storage_account_name      = azurerm_storage_account.lake.name
  storage_account_key       = azurerm_storage_account.lake.primary_access_key
  storage_container_name    = azurerm_storage_container.main["reference"].name
  path_pattern              = each.key
  date_format               = "yyyy/MM/dd"
  time_format               = "HH"

  serialization {
    type            = "Csv"
    encoding        = "UTF8"
    field_delimiter = ","
  }
}

# Durable outputs into the data lake, partitioned by date and hour so Synapse
# serverless can read only the hours it needs.
locals {
  asa_outputs = {
    raw_archive = "Parquet"
    kpi_1min    = "Json"
  }
}

resource "azurerm_stream_analytics_output_blob" "main" {
  for_each                  = local.asa_outputs
  name                      = each.key
  stream_analytics_job_name = azurerm_stream_analytics_job.main.name
  resource_group_name       = data.azurerm_resource_group.main.name
  storage_account_name      = azurerm_storage_account.lake.name
  storage_account_key       = azurerm_storage_account.lake.primary_access_key
  storage_container_name    = azurerm_storage_container.main["lake"].name
  path_pattern              = "${each.key}/{date}/{time}"
  date_format               = "yyyy/MM/dd"
  time_format               = "HH"
  # Parquet requires a batch: a file is written at 2,000 rows or after 1 minute (portal defaults).
  batch_min_rows      = each.value == "Parquet" ? 2000 : null
  batch_max_wait_time = each.value == "Parquet" ? "00:01:00" : null

  serialization {
    type     = each.value
    encoding = each.value == "Json" ? "UTF8" : null
    format   = each.value == "Json" ? "LineSeparated" : null
  }
}

# SQL output tables are created by scripts/sql/create_asa_output_tables.sql.
# After Terraform creates the job identity, run the permission script once as
# the SQL Entra administrator before starting ASA.
locals {
  asa_sql_outputs = {
    kpi_1min_sql     = "dbo.kpi_1min"
    pipeline_latency = "dbo.pipeline_latency"
  }
}

resource "azurerm_stream_analytics_output_mssql" "main" {
  for_each = local.asa_sql_outputs

  name                      = each.key
  resource_group_name       = data.azurerm_resource_group.main.name
  stream_analytics_job_name = azurerm_stream_analytics_job.main.name
  server                    = azurerm_mssql_server.main.fully_qualified_domain_name
  database                  = azapi_resource.sql_db.name
  table                     = each.value
  authentication_mode       = "Msi"
  max_batch_count           = 1000
  max_writer_count          = 1
}

# The Power BI connector uses the same system-assigned identity as the SQL
# outputs. A workspace administrator must add asa-megasale-dev as Contributor.
resource "azurerm_stream_analytics_output_powerbi" "kpi_1min" {
  name                    = "kpi_1min_powerbi"
  stream_analytics_job_id = azurerm_stream_analytics_job.main.id
  group_id                = "103d1909-ed9d-45d5-97d8-6c7581fc0065"
  group_name              = "Megasale-powerBI"
  dataset                 = "megasale_kpi_1min"
  table                   = "kpi_1min"
}
