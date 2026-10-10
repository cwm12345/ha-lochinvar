"""Test setting up and tearing down the Lochinvar integration."""

# Written by Claude, guided by Chris.

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusConnection
from tests.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

OUTLET = "sensor.boiler_outlet_temperature"
TANK = "sensor.boiler_tank_temperature"


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The entry loads, creates entities, and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert hass.states.get(OUTLET).state == "98.6"

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """A boiler that answers nothing makes setup retry rather than fail."""
    mock_connection.for_unit(1).fail_requests(ModbusTimeoutError())
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.lochinvar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_a_refused_table_only_hides_its_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A refused holding-register block hides the tank sensor, not the outlet."""
    mock_connection.for_unit(1).fail_read(0, IllegalDataAddressError())
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TANK).state == STATE_UNAVAILABLE
    assert hass.states.get(OUTLET).state == "98.6"


async def test_a_dead_link_recovers(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A dropped link makes readings unavailable until the next good poll."""
    unit = mock_connection.for_unit(1)
    unit.fail_requests(ModbusConnectionError())
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(OUTLET).state == STATE_UNAVAILABLE
    assert init_integration.state is ConfigEntryState.LOADED

    unit.fail_requests(None)
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(OUTLET).state == "98.6"
