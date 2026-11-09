# Stream Analytics job. Terraform creates it stopped: billed only while running,
# so start it for a test and stop it right after (see README).
# The query lives in stream/query.asaql (owned by Thắng); changing it updates the job,
# which only works while the job is stopped.
resource "azurerm_stream_analytics_job" "main" {
  name                = "asa-${local.name}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.main.name
  sku_name            = "StandardV2"
  streaming_units     = 1 # V2: 1 = the smallest size (1/3 SU)
  compatibility_level = "1.2"
  data_locale         = "en-US"
  output_error_policy = "Stop"

  # Event time policy: Thắng finalizes these in #37.
  events_late_arrival_max_delay_in_seconds = 5
  events_out_of_order_max_delay_in_seconds = 0
  events_out_of_order_policy               = "Adjust"

  transformation_query = file("${path.module}/../stream/query.asaql")
  tags                 = local.tags
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

# Outputs into the data lake, one folder per output, partitioned by date and hour
# so Synapse serverless can read only the hours it needs.
# kpi_1min goes to the lake for now; SQL and Power BI outputs come after #35.
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

  serialization {
    type     = each.value
    encoding = each.value == "Json" ? "UTF8" : null
    format   = each.value == "Json" ? "LineSeparated" : null
  }
}
