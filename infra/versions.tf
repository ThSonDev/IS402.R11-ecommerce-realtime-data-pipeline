terraform {
  required_version = ">= 1.16"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "rg-megasale-dev"
    storage_account_name = "stmegasaletf2911"
    container_name       = "tfstate"
    key                  = "megasale.tfstate"
    use_azuread_auth     = true
  }
}
