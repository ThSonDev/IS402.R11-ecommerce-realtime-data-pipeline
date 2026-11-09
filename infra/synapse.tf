# Synapse workspace for the serverless SQL pool only (billed per TB scanned, no idle cost).
# Never add a dedicated SQL pool or Spark pool here.
resource "azurerm_synapse_workspace" "main" {
  name                                 = "synw-${local.name}"
  location                             = var.location
  resource_group_name                  = data.azurerm_resource_group.main.name
  storage_data_lake_gen2_filesystem_id = "${azurerm_storage_account.lake.primary_dfs_endpoint}${azurerm_storage_container.main["synapse"].name}"
  azuread_authentication_only          = true
  tags                                 = local.tags

  identity {
    type = "SystemAssigned"
  }

  # Azure fills in a default SQL login even with Entra-only auth; without this,
  # every plan would destroy and re-create the workspace.
  lifecycle {
    ignore_changes = [sql_administrator_login]
  }
}

resource "azurerm_synapse_workspace_aad_admin" "main" {
  synapse_workspace_id = azurerm_synapse_workspace.main.id
  login                = var.sql_admin.login
  object_id            = var.sql_admin.object_id
  tenant_id            = var.sql_admin.tenant_id
}

# Same reasoning as the SQL firewall rule: Entra ID login only, member IPs change.
resource "azurerm_synapse_firewall_rule" "all" {
  name                 = "allow-all"
  synapse_workspace_id = azurerm_synapse_workspace.main.id
  start_ip_address     = "0.0.0.0"
  end_ip_address       = "255.255.255.255"
}
