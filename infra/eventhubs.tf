# Event Hubs Standard: Basic has no Kafka endpoint. Billed per TU-hour while it exists,
# so destroy it when not testing (see README).
resource "azurerm_eventhub_namespace" "main" {
  name                = "evhns-${local.name}"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.main.name
  sku                 = "Standard"
  capacity            = 1 # 1 TU = 1,000 events/s in
  minimum_tls_version = "1.2"
  tags                = local.tags
}

# Kafka topic = event hub. Partition count can't change later on Standard.
resource "azurerm_eventhub" "events" {
  name              = "events"
  namespace_id      = azurerm_eventhub_namespace.main.id
  partition_count   = 4
  message_retention = 1
}

# Stream Analytics reads with its own consumer group, so other readers don't steal its offsets.
resource "azurerm_eventhub_consumer_group" "asa" {
  name                = "asa"
  namespace_name      = azurerm_eventhub_namespace.main.name
  eventhub_name       = azurerm_eventhub.events.name
  resource_group_name = data.azurerm_resource_group.main.name
}

# One policy per app, least privilege: the producer can only send, ASA can only listen.
resource "azurerm_eventhub_authorization_rule" "producer" {
  name                = "producer-send"
  namespace_name      = azurerm_eventhub_namespace.main.name
  eventhub_name       = azurerm_eventhub.events.name
  resource_group_name = data.azurerm_resource_group.main.name
  send                = true
  listen              = false
  manage              = false
}

resource "azurerm_eventhub_authorization_rule" "asa" {
  name                = "asa-listen"
  namespace_name      = azurerm_eventhub_namespace.main.name
  eventhub_name       = azurerm_eventhub.events.name
  resource_group_name = data.azurerm_resource_group.main.name
  send                = false
  listen              = true
  manage              = false
}
