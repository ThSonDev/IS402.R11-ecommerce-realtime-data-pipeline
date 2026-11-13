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

# Synapse RBAC (data plane, not an Azure role): only the workspace creator (the CI app)
# has it by default, so even the Entra admin cannot log in to serverless without this.
locals {
  synapse_roles = {
    son   = { id = var.sql_admin.object_id, role = "Synapse Administrator" }
    minh  = { id = "24f68d05-4084-4bb0-b74d-0a6b199a5e4c", role = "Synapse SQL Administrator" }
    thang = { id = "9986ca58-9224-4bae-9e94-c97de889b326", role = "Synapse SQL Administrator" }
    tuan  = { id = "6daaaf33-7187-4c2d-9e03-27517fe412d0", role = "Synapse SQL Administrator" }
  }
}

resource "azurerm_synapse_role_assignment" "main" {
  for_each             = local.synapse_roles
  synapse_workspace_id = azurerm_synapse_workspace.main.id
  role_name            = each.value.role
  principal_id         = each.value.id
  principal_type       = "User"

  depends_on = [azurerm_synapse_firewall_rule.all] # CI calls the workspace endpoint
}
