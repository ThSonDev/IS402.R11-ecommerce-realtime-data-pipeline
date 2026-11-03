variable "resource_group_name" {
  type    = string
  default = "rg-megasale-dev"
}

variable "location" {
  type    = string
  default = "japaneast"

  validation {
    condition     = contains(["japaneast", "japanwest", "koreacentral", "centralindia", "indonesiacentral"], var.location)
    error_message = "Azure for Students only allows japaneast, japanwest, koreacentral, centralindia, indonesiacentral."
  }
}

variable "project" {
  type    = string
  default = "megasale"
}

variable "env" {
  type    = string
  default = "dev"
}

# Entra ID admin of Azure SQL and Synapse (not a secret: IDs only).
# Set explicitly because in CI the caller is the GitHub app, not Sơn.
variable "sql_admin" {
  type = object({
    login     = string
    object_id = string
    tenant_id = string
  })
  default = {
    login     = "23521360@ms.uit.edu.vn"
    object_id = "b2c0b8ba-9009-4b7f-8d7b-86d872ef3239"
    tenant_id = "2dff09ac-2b3b-4182-9953-2b548e0d0b39"
  }
}
