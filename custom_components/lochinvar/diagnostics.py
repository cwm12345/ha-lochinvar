"""Diagnostics for Lochinvar boilers."""

# Written by Claude, guided by Chris.

from __future__ import annotations

from typing import Any

from modbus_connection import ModbusError

from homeassistant.core import HomeAssistant

from .coordinator import LochinvarConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LochinvarConfigEntry
) -> dict[str, Any]:
    """Return the raw register tables and the latest poll's outcome.

    The board holds no serial number or other personal information, so nothing
    needs redacting from the registers. The gateway address is left out.
    """
    coordinator = entry.runtime_data
    device = coordinator.device
    try:
        registers: dict[str, Any] = await device.async_read_raw()
    except ModbusError as err:
        registers = {"error": str(err) or type(err).__name__}
    feed = coordinator.outdoor_feed
    return {
        "temperature_unit": device.temperature_unit.value,
        "outdoor_feed": None
        if feed is None
        else {
            "source": feed.source,
            "feeding": feed.feeding,
            "last_value": feed.last_value,
        },
        "updated": sorted(coordinator.data.updated),
        "failed": {k: str(v) for k, v in coordinator.data.failed.items()},
        "registers": registers,
    }
