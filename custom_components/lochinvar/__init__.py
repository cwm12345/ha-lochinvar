"""The Lochinvar boiler integration."""

# Written by Claude, guided by Chris.

from __future__ import annotations

from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_TEMPERATURE_UNIT, CONF_UNIT_ID
from .coordinator import LochinvarConfigEntry, LochinvarCoordinator
from .lochinvar_modbus import LochinvarBoiler, TemperatureUnit

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


def unique_id_for(host: str, port: int, unit_id: int) -> str:
    """Return the config entry unique ID for one boiler behind one gateway port."""
    return f"{host}:{port}:{unit_id}"


async def async_setup_entry(hass: HomeAssistant, entry: LochinvarConfigEntry) -> bool:
    """Set up a Lochinvar boiler from a config entry."""
    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]),
        entry.data[CONF_UNIT_ID],
    )
    device = LochinvarBoiler(unit, TemperatureUnit(entry.data[CONF_TEMPERATURE_UNIT]))
    coordinator = LochinvarCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LochinvarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
