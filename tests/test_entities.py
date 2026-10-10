"""Test the Lochinvar entities."""

# Written by Claude, guided by Chris.

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection.mock import MockModbusConnection
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.lochinvar.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_UNIQUE_ID, MOCK_USER_INPUT


@pytest.mark.parametrize(
    ("entity_id", "state"),
    [
        ("sensor.boiler_outlet_temperature", "98.6"),
        ("sensor.boiler_inlet_temperature", "97.1"),
        ("sensor.boiler_flue_temperature", "84.3"),
        ("sensor.boiler_outlet_setpoint", STATE_UNKNOWN),
        ("sensor.boiler_tank_temperature", "119.6"),
        ("sensor.boiler_tank_setpoint", "124.0"),
        ("sensor.boiler_outdoor_temperature", "62.9"),
        ("sensor.boiler_firing_rate", "0"),
        ("sensor.boiler_pump_speed", "9"),
        ("sensor.boiler_system_pump_speed", "0"),
        ("sensor.boiler_status", "heating_pump_delay"),
        ("sensor.boiler_status_code", "33"),
        ("sensor.boiler_blocking", "none"),
        ("sensor.boiler_blocking_code", "0"),
        ("sensor.boiler_lockout_reason", STATE_UNKNOWN),
        ("sensor.boiler_lockout_code", STATE_UNKNOWN),
        ("sensor.boiler_bms_configuration", "0"),
        ("sensor.boiler_bms_command", "0"),
        ("sensor.boiler_rate_command", "0"),
        ("binary_sensor.boiler_ch_pump", STATE_ON),
        ("binary_sensor.boiler_flame", STATE_OFF),
        ("binary_sensor.boiler_gas_valve", STATE_OFF),
        ("binary_sensor.boiler_flow_switch", STATE_ON),
        ("binary_sensor.boiler_air_pressure_switch", STATE_ON),
        ("binary_sensor.boiler_auto_reset_high_limit", STATE_OFF),
        ("binary_sensor.boiler_dhw_recirculation_pump", STATE_OFF),
        ("binary_sensor.boiler_room_thermostat_1_demand", STATE_OFF),
        ("binary_sensor.boiler_run_time_contacts", STATE_OFF),
        ("binary_sensor.boiler_lockout", STATE_OFF),
    ],
)
async def test_entity_states(
    hass: HomeAssistant, init_integration: MockConfigEntry, entity_id: str, state: str
) -> None:
    """Every entity decodes the live boiler's registers."""
    assert hass.states.get(entity_id).state == state


async def test_temperatures_are_in_the_boilers_unit(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A Fahrenheit boiler's temperatures are native Fahrenheit."""
    state = hass.states.get("sensor.boiler_outlet_temperature")
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.FAHRENHEIT


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.boiler_system_supply_temperature",
        "sensor.boiler_system_setpoint",
        "sensor.boiler_dhw_recirculation_temperature",
        "sensor.boiler_cascade_total_power",
        "sensor.boiler_cascade_current_power",
    ],
)
async def test_absent_sensors_create_no_entity(
    hass: HomeAssistant, init_integration: MockConfigEntry, entity_id: str
) -> None:
    """Open-circuit sensors and a lone boiler's cascade values get no entity."""
    assert hass.states.get(entity_id) is None


async def test_connected_sensors_are_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """A connected system sensor brings its temperature and setpoint."""
    unit = mock_connection.for_unit(1)
    unit.holding[6] = 1402  # system supply 140.2 F
    unit.input[3] = 135  # system setpoint 135 F
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.lochinvar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get("sensor.boiler_system_supply_temperature").state == "140.2"
    assert hass.states.get("sensor.boiler_system_setpoint").state == "135.0"


async def test_lockout(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Status 40 raises the lockout problem and names the reason."""
    unit = mock_connection.for_unit(1)
    unit.input[13] = 40
    unit.input[15] = 233
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.boiler_lockout").state == STATE_ON
    assert hass.states.get("sensor.boiler_status").state == "lockout"
    assert (
        hass.states.get("sensor.boiler_lockout_reason").state
        == "no_flame_after_ignition"
    )
    assert hass.states.get("sensor.boiler_lockout_code").state == "233"


async def test_firing_for_hot_water(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Setpoints are whole degrees and rates whole percent."""
    unit = mock_connection.for_unit(1)
    unit.input[7] = 170
    unit.input[11] = 57
    unit.input[13] = 19
    unit.input[0] = 62 | 1 << 7 | 1 << 9  # + flame, tank thermostat
    unit.input[2] = 4 | 1 << 5 | 1 << 3  # + gas valve, DHW pump
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.boiler_outlet_setpoint").state == "170.0"
    assert hass.states.get("sensor.boiler_firing_rate").state == "57"
    assert hass.states.get("sensor.boiler_status").state == "hot_water"
    for name in ("flame", "tank_thermostat_demand", "gas_valve", "dhw_pump"):
        assert hass.states.get(f"binary_sensor.boiler_{name}").state == STATE_ON


async def test_an_unlisted_status_reads_unknown(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A code the manual doesn't list leaves the decoded status unknown."""
    mock_connection.for_unit(1).input[13] = 77
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.boiler_status").state == STATE_UNKNOWN
    assert hass.states.get("sensor.boiler_status_code").state == "77"


async def test_celsius_boiler(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """A Celsius boiler is decoded per the manual and reported in Celsius."""
    unit = mock_connection.for_unit(1)
    unit.input[8] = 683  # 68.3 C, the manual's example
    unit.holding[3] = 120  # tank setpoint 60.0 C, half degrees
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_UNIQUE_ID,
        data={**MOCK_USER_INPUT, "temperature_unit": "°C"},
        title=DEFAULT_NAME,
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.lochinvar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    outlet = hass.states.get("sensor.boiler_outlet_temperature")
    assert float(outlet.state) == pytest.approx(154.94, abs=0.01)  # shown in F
    assert outlet.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.FAHRENHEIT
    assert hass.states.get("sensor.boiler_tank_setpoint").state == "140.0"


async def test_unique_ids_keep_their_keys(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Unique IDs are the entry ID plus a stable key."""
    entry = entity_registry.async_get("sensor.boiler_pump_speed")
    assert entry.unique_id == f"{init_integration.entry_id}_pump_speed"


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Diagnostics carry the raw tables and the temperature unit."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    assert result["temperature_unit"] == "°F"
    assert result["registers"]["input"]["13"] == 33
    assert result["registers"]["holding"]["3"] == 124
    assert result["failed"] == {}
