# Azure SQL with Entra ID login only: no SQL password exists, so there is no secret to share.
# Each member logs in with their own school account (added as a DB user, see README).
resource "azurerm_mssql_server" "main" {
  name                = "sql-${local.name}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.main.name
  version             = "12.0"
  minimum_tls_version = "1.2"
  tags                = local.tags

  azuread_administrator {
    login_username              = var.sql_admin.login
    object_id                   = var.sql_admin.object_id
    azuread_authentication_only = true
  }
}

# Members' home IPs change, and login needs Entra ID anyway.
# ponytail: open to all IPs; add per-member rules if the lecturer asks for tighter network rules.
resource "azurerm_mssql_firewall_rule" "all" {
  name             = "allow-all"
  server_id        = azurerm_mssql_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "255.255.255.255"
}

# azurerm has no free-offer setting yet, so this one resource goes through azapi.
# Free offer: 100,000 vCore-seconds + 32 GB per month, then AutoPause until next month (never bills).
resource "azapi_resource" "sql_db" {
  type      = "Microsoft.Sql/servers/databases@2023-08-01"
  name      = "sqldb-${local.name}"
  parent_id = azurerm_mssql_server.main.id
  location  = var.location
  tags      = local.tags

  body = {
    sku = {
      name     = "GP_S_Gen5"
      tier     = "GeneralPurpose"
      family   = "Gen5"
      capacity = 2
    }
    properties = {
      useFreeLimit                     = true
      freeLimitExhaustionBehavior      = "AutoPause"
      maxSizeBytes                     = 34359738368 # 32 GB
      requestedBackupStorageRedundancy = "Local"
    }
  }
}
