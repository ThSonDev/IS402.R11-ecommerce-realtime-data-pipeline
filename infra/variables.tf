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
