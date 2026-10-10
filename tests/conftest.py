"""Common fixtures for the Lochinvar tests."""

# Written by Claude, guided by Chris.

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from modbus_connection.mock import MockModbusConnection
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lochinvar.const import DEFAULT_NAME, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import MOCK_UNIQUE_ID, MOCK_USER_INPUT, seed_boiler


@pytest.fixture(autouse=True)
def us_customary_units(hass: HomeAssistant) -> None:
    """Show temperatures in Fahrenheit, like the boiler's display."""
    hass.config.units = US_CUSTOMARY_SYSTEM


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.lochinvar.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connection() -> MockModbusConnection:
    """Return a fake Modbus TCP connection seeded as the live boiler."""
    connection = MockModbusConnection()
    seed_boiler(connection.for_unit(1))
    return connection


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Lochinvar config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_UNIQUE_ID,
        data=MOCK_USER_INPUT,
        title=DEFAULT_NAME,
        version=1,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> MockConfigEntry:
    """Set up the integration against the mock connection."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.lochinvar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the custom integration in every test."""
