# The resource group is created by hand (it also holds the state and IAM),
# so Terraform only reads it.
data "azurerm_resource_group" "main" {
  name = var.resource_group_name
}

locals {
  # Resource names follow <type>-megasale-dev, e.g. evhns-megasale-dev.
  name = "${var.project}-${var.env}"

  tags = {
    project    = "is402"
    managed_by = "terraform"
  }
}
