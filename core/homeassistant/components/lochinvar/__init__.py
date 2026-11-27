"""The Lochinvar boiler integration."""

# Written by Claude, guided by Chris.

from __future__ import annotations

from lochinvar_modbus import LochinvarBoiler, TemperatureUnit
from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_OUTDOOR_TEMPERATURE_SOURCE, CONF_TEMPERATURE_UNIT, CONF_UNIT_ID
from .coordinator import LochinvarConfigEntry, LochinvarCoordinator
from .outdoor_feed import OutdoorTemperatureFeed

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
    if source := entry.options.get(CONF_OUTDOOR_TEMPERATURE_SOURCE):
        coordinator.outdoor_feed = OutdoorTemperatureFeed(hass, coordinator, source)
        coordinator.outdoor_feed.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: LochinvarConfigEntry
) -> None:
    """Reload so a new outdoor temperature source takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: LochinvarConfigEntry) -> bool:
    """Unload a config entry, handing the outdoor temperature back first."""
    if (feed := entry.runtime_data.outdoor_feed) is not None:
        await feed.async_stop()
        entry.runtime_data.outdoor_feed = None
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
