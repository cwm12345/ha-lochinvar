"""Feed the boiler an outdoor temperature from another Home Assistant sensor."""

# Written by Claude, guided by Chris.

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from lochinvar_modbus import TemperatureUnit
from modbus_connection import ModbusError

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import FEED_INTERVAL
from .coordinator import LochinvarCoordinator

_LOGGER = logging.getLogger(__name__)

_HA_UNIT = {
    TemperatureUnit.FAHRENHEIT: UnitOfTemperature.FAHRENHEIT,
    TemperatureUnit.CELSIUS: UnitOfTemperature.CELSIUS,
}

# What gets written, clamped to what the library will encode. Fahrenheit stops
# at 32 F: sub-zero writes are unverified, and a reset curve is at its cap
# long before then, so the boiler behaves the same.
_CLAMP = {
    TemperatureUnit.FAHRENHEIT: (32.0, 140.0),
    TemperatureUnit.CELSIUS: (-40.0, 60.0),
}


class OutdoorTemperatureFeed:
    """Write a sensor's temperature into the boiler in place of its outdoor sensor.

    For a boiler whose own outdoor sensor reads wrong, typically because it
    sits in sun. The boiler keeps the fed value only while it's refreshed
    within its ModBus timeout, so this writes every few seconds. When the
    source has no usable value, or this stops, the boiler goes back to its own
    sensor.
    """

    def __init__(
        self, hass: HomeAssistant, coordinator: LochinvarCoordinator, source: str
    ) -> None:
        """Initialize the feed."""
        self.hass = hass
        self.coordinator = coordinator
        self.source = source
        self.feeding = False
        self.last_value: float | None = None
        self._unsub: CALLBACK_TYPE | None = None
        self._lock = asyncio.Lock()
        self._error_logged = False

    @property
    def _unit(self) -> TemperatureUnit:
        return self.coordinator.device.temperature_unit

    @callback
    def async_start(self) -> None:
        """Start writing every FEED_INTERVAL seconds."""
        self._unsub = async_track_time_interval(
            self.hass,
            self._async_tick,
            timedelta(seconds=FEED_INTERVAL),
            name="Lochinvar outdoor temperature feed",
            cancel_on_shutdown=True,
        )

    async def async_stop(self) -> None:
        """Stop writing and hand the outdoor temperature back to the boiler."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        async with self._lock:
            if self.feeding:
                await self._async_release("the feed was stopped")

    def source_value(self) -> float | None:
        """Return the source's temperature in the boiler's unit, or None."""
        state = self.hass.states.get(self.source)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            value = float(state.state)
        except ValueError:
            return None
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit not in TemperatureConverter.VALID_UNITS:
            return None
        return TemperatureConverter.convert(value, unit, _HA_UNIT[self._unit])

    async def _async_tick(self, now: datetime | None = None) -> None:
        """Write the source's current value, or release if it has none."""
        if self._lock.locked():
            return  # the previous write is still waiting on the gateway
        async with self._lock:
            value = self.source_value()
            if value is None:
                if self.feeding:
                    await self._async_release(f"{self.source} has no usable value")
                return
            low, high = _CLAMP[self._unit]
            value = round(min(max(value, low), high), 1)
            try:
                await self.coordinator.device.bms.async_feed_outdoor_temperature(value)
            except ModbusError as err:
                if not self._error_logged:
                    _LOGGER.warning(
                        "%s: could not write the outdoor temperature, so the boiler"
                        " will fall back to its own sensor: %s",
                        self.coordinator.name,
                        err,
                    )
                    self._error_logged = True
                return
            if self._error_logged or not self.feeding:
                _LOGGER.info(
                    "%s: feeding the outdoor temperature from %s",
                    self.coordinator.name,
                    self.source,
                )
            self._error_logged = False
            self.feeding = True
            self.last_value = value

    async def _async_release(self, why: str) -> None:
        """Clear the outdoor bit so the boiler uses its own sensor again."""
        self.feeding = False
        self.last_value = None
        try:
            await self.coordinator.device.bms.async_release_outdoor_temperature()
        except ModbusError as err:
            _LOGGER.warning(
                "%s: %s, and releasing the outdoor temperature failed (%s); the"
                " boiler falls back to its own sensor at its ModBus timeout",
                self.coordinator.name,
                why,
                err,
            )
            return
        _LOGGER.warning(
            "%s: %s; the boiler is back on its own outdoor sensor",
            self.coordinator.name,
            why,
        )
