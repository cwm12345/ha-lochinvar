"""Test feeding the boiler an outdoor temperature from another sensor."""

# Written by Claude, guided by Chris.

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest
from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

from homeassistant.components.lochinvar.const import (
    CONF_OUTDOOR_TEMPERATURE_SOURCE,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_UNIQUE_ID, MOCK_USER_INPUT

SOURCE = "sensor.outdoor_best"
FED = "binary_sensor.boiler_outdoor_temperature_fed"
OUTDOOR = "sensor.boiler_outdoor_temperature"
_F = {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Lochinvar config entry that feeds the outdoor temperature."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_UNIQUE_ID,
        data=MOCK_USER_INPUT,
        options={CONF_OUTDOOR_TEMPERATURE_SOURCE: SOURCE},
        title=DEFAULT_NAME,
        version=1,
    )


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: int = 3
) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_feeds_the_source_every_few_seconds(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The source's value goes into 40006 and the outdoor bit into 40001."""
    unit = mock_connection.for_unit(1)
    hass.states.async_set(SOURCE, "41.46", _F)
    await _tick(hass, freezer)
    assert unit.holding[5] == 415
    assert unit.holding[0] == 32

    hass.states.async_set(SOURCE, "43.0", _F)
    await _tick(hass, freezer)
    assert unit.holding[5] == 430

    # The next poll sees the boiler using the fed value.
    await _tick(hass, freezer, 30)
    assert hass.states.get(FED).state == STATE_ON
    assert hass.states.get(OUTDOOR).state == "43.0"


async def test_celsius_source_is_converted(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A Celsius source is written in the boiler's Fahrenheit."""
    hass.states.async_set(
        SOURCE, "5.0", {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    await _tick(hass, freezer)
    assert mock_connection.for_unit(1).holding[5] == 410


async def test_cold_values_are_clamped_to_freezing(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Below 32 F is written as 32 F, the lowest checked encoding."""
    hass.states.async_set(SOURCE, "12.0", _F)
    await _tick(hass, freezer)
    assert mock_connection.for_unit(1).holding[5] == 320


@pytest.mark.parametrize(
    "unusable",
    [
        (STATE_UNAVAILABLE, _F),
        ("not a number", _F),
        ("40.0", {}),
    ],
)
async def test_an_unusable_source_hands_back_to_the_sensor(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
    unusable: tuple[str, dict[str, str]],
) -> None:
    """With no usable value the outdoor bit is cleared, once."""
    unit = mock_connection.for_unit(1)
    hass.states.async_set(SOURCE, "41.0", _F)
    await _tick(hass, freezer)
    assert unit.holding[0] == 32

    hass.states.async_set(SOURCE, *unusable)
    await _tick(hass, freezer)
    assert unit.holding[0] == 0
    assert unit.holding[5] == 410  # left as last written; the boiler ignores it

    hass.states.async_set(SOURCE, "42.0", _F)
    await _tick(hass, freezer)
    assert unit.holding[0] == 32
    assert unit.holding[5] == 420


async def test_nothing_is_written_before_the_source_has_a_value(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A missing source never touches the boiler."""
    await _tick(hass, freezer)
    unit = mock_connection.for_unit(1)
    assert unit.holding[0] == 0
    assert unit.holding[5] == 629


async def test_a_failed_write_keeps_trying(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A gateway timeout is logged, and the next tick writes again."""
    unit = mock_connection.for_unit(1)
    hass.states.async_set(SOURCE, "41.0", _F)
    unit.fail_requests(ModbusTimeoutError())
    await _tick(hass, freezer)
    assert unit.holding[0] == 0

    unit.fail_requests(None)
    await _tick(hass, freezer)
    assert unit.holding[0] == 32


async def test_unload_hands_back_to_the_sensor(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unloading clears the outdoor bit and stops writing."""
    unit = mock_connection.for_unit(1)
    hass.states.async_set(SOURCE, "41.0", _F)
    await _tick(hass, freezer)
    assert unit.holding[0] == 32

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED
    assert unit.holding[0] == 0

    await _tick(hass, freezer)
    assert unit.holding[0] == 0


async def test_diagnostics_show_the_feed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Diagnostics name the source and the last value written."""
    hass.states.async_set(SOURCE, "41.0", _F)
    await _tick(hass, freezer)
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    assert result["outdoor_feed"] == {
        "source": SOURCE,
        "feeding": True,
        "last_value": 41.0,
    }


async def test_options_flow_sets_and_clears_the_source(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Clearing the source in the options stops the feed after the reload."""
    unit = mock_connection.for_unit(1)
    hass.states.async_set(SOURCE, "41.0", _F)
    await _tick(hass, freezer)
    assert unit.holding[0] == 32

    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    with patch(
        "homeassistant.components.lochinvar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.options == {}
    assert unit.holding[0] == 0

    await _tick(hass, freezer)
    assert unit.holding[0] == 0
    assert hass.states.get(FED).state == STATE_OFF
