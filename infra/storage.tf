# ADLS Gen2 (hierarchical namespace on): reference data for ASA, data lake for ASA output,
# and the default filesystem Synapse requires.
resource "azurerm_storage_account" "lake" {
  name                            = "st${var.project}${var.env}"
  location                        = var.location
  resource_group_name             = data.azurerm_resource_group.main.name
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  is_hns_enabled                  = true
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  tags                            = local.tags
}

resource "azurerm_storage_container" "main" {
  for_each           = toset(["reference", "lake", "synapse"])
  name               = each.key
  storage_account_id = azurerm_storage_account.lake.id
}

# Re-uploaded whenever the file changes (content_md5), so Git stays the source of truth.
resource "azurerm_storage_blob" "provinces" {
  name                 = "provinces.csv"
  storage_container_id = azurerm_storage_container.main["reference"].id
  type                 = "Block"
  source               = "${path.module}/../stream/reference/provinces.csv"
  content_md5          = filemd5("${path.module}/../stream/reference/provinces.csv")
}
