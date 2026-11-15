output "resource_group_id" {
  value = data.azurerm_resource_group.main.id
}

# Names and endpoints only. Keys and connection strings are fetched with az (scripts/fill_env.py).
output "kafka_bootstrap_servers" {
  value = "${azurerm_eventhub_namespace.main.name}.servicebus.windows.net:9093"
}

output "lake_dfs_endpoint" {
  value = azurerm_storage_account.lake.primary_dfs_endpoint
}

output "sql_server_fqdn" {
  value = azurerm_mssql_server.main.fully_qualified_domain_name
}

output "synapse_serverless_endpoint" {
  value = azurerm_synapse_workspace.main.connectivity_endpoints["sqlOnDemand"]
}

# Give this principal Contributor access to the Power BI workspace for the ASA
# managed-identity Power BI output.
output "asa_principal_id" {
  value = azurerm_stream_analytics_job.main.identity[0].principal_id
}
