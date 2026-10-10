"""Config flow for Lochinvar boilers."""

# Written by Claude, guided by Chris.

from __future__ import annotations

import logging
from typing import Any

from modbus_connection import ModbusError, ModbusTcpParams
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from . import unique_id_for
from .const import (
    CONF_TEMPERATURE_UNIT,
    CONF_UNIT_ID,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from .lochinvar_modbus import LochinvarBoiler, TemperatureUnit

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            vol.Coerce(int),
        ),
        vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): vol.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)
            ),
            vol.Coerce(int),
        ),
        vol.Required(
            CONF_TEMPERATURE_UNIT, default=TemperatureUnit.FAHRENHEIT.value
        ): SelectSelector(
            SelectSelectorConfig(
                options=[unit.value for unit in TemperatureUnit],
                mode=SelectSelectorMode.LIST,
            )
        ),
    }
)


async def _async_probe(
    hass: HomeAssistant, host: str, port: int, unit_id: int, unit: TemperatureUnit
) -> None:
    """Read the boiler once over a temporary unit, or raise."""
    params = ModbusTcpParams(host=host, port=port)
    async with async_get_temporary_unit(hass, params, unit_id) as modbus_unit:
        report = await LochinvarBoiler(modbus_unit, unit).async_update()
    if not report.updated:
        raise next(iter(report.failed.values()))


class LochinvarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Lochinvar boiler config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the gateway, unit ID and display unit; check the boiler answers."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            unit_id = user_input[CONF_UNIT_ID]
            await self.async_set_unique_id(unique_id_for(host, port, unit_id))
            self._abort_if_unique_id_configured()
            try:
                await _async_probe(
                    self.hass,
                    host,
                    port,
                    unit_id,
                    TemperatureUnit(user_input[CONF_TEMPERATURE_UNIT]),
                )
            except (ModbusError, HomeAssistantError) as err:
                _LOGGER.debug("Could not read the boiler: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
