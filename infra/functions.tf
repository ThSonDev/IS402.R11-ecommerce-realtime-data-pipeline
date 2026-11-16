# Function App for fraud alerts -> Telegram (code in functions/fraud_alert, owned by Minh).
# Linux Consumption (Y1): billed per execution, inside the free grant for this project,
# no cost while idle, so it stays up across destroy-eventhubs.
# Flex Consumption is newer, but ASA's Functions output is documented only for classic plans.

# Separate storage for the Functions host: the lake account has a hierarchical namespace,
# which the Functions runtime does not need, and this keeps the lake clean.
resource "azurerm_storage_account" "func" {
  name                            = "st${var.project}func"
  location                        = var.location
  resource_group_name             = data.azurerm_resource_group.main.name
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  tags                            = local.tags
}

resource "azurerm_service_plan" "func" {
  name                = "asp-${local.name}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.main.name
  os_type             = "Linux"
  sku_name            = "Y1"
  tags                = local.tags
}

resource "azurerm_linux_function_app" "main" {
  name                = "func-${local.name}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.main.name
  service_plan_id     = azurerm_service_plan.func.id
  # Storage key auth: managed identity would need a role assignment the CI app can't create.
  storage_account_name       = azurerm_storage_account.func.name
  storage_account_access_key = azurerm_storage_account.func.primary_access_key
  https_only                 = true
  tags                       = local.tags

  site_config {
    application_stack {
      python_version = "3.12"
    }
  }

  # Secrets are set by hand (see infra/README.md), never in Git or tfvars.
  app_settings = {
    TELEGRAM_BOT_TOKEN = ""
    TELEGRAM_CHAT_ID   = ""
    # Zip deploy installs requirements.txt on Azure (az sets it too; declared to avoid drift).
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
  }

  lifecycle {
    ignore_changes = [
      app_settings["TELEGRAM_BOT_TOKEN"],
      app_settings["TELEGRAM_CHAT_ID"],
      # Set by every code deploy (zip package URL); Terraform must not remove it.
      app_settings["WEBSITE_RUN_FROM_PACKAGE"],
    ]
  }
}
