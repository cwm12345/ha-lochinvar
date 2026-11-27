"""Constants for the Lochinvar boiler integration."""

# Written by Claude, guided by Chris.

DOMAIN = "lochinvar"

MANUFACTURER = "Lochinvar"
MODEL = "Boiler with MODB-I-O board"
DEFAULT_NAME = "Boiler"

CONF_UNIT_ID = "unit_id"
CONF_TEMPERATURE_UNIT = "temperature_unit"
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1

SCAN_INTERVAL = 30

CONF_OUTDOOR_TEMPERATURE_SOURCE = "outdoor_temperature_source"
FEED_INTERVAL = 30
"""Seconds between outdoor temperature writes. The manual asks for a refresh
at least every 4 minutes; a live boiler kept an unrefreshed value 5 min 10 s."""
