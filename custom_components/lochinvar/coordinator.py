"""Data update coordinator for Lochinvar boilers."""

# Written by Claude, guided by Chris.

from __future__ import annotations

from datetime import timedelta
import logging

from modbus_connection import ModbusError
from modbus_connection.model import UpdateReport

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MANUFACTURER, MODEL, SCAN_INTERVAL
from .lochinvar_modbus import LochinvarBoiler

_LOGGER = logging.getLogger(__name__)

type LochinvarConfigEntry = ConfigEntry[LochinvarCoordinator]


class LochinvarCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Poll both register tables of one boiler."""

    config_entry: LochinvarConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: LochinvarConfigEntry, device: LochinvarBoiler
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.device = device
        self._failed: frozenset[str] = frozenset()
        # The board reports no serial number; the config entry is its identity.
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self.device.async_update()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
                translation_placeholders={"error": str(err) or type(err).__name__},
            ) from err
        if not report.updated:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_component_answered",
            ) from ExceptionGroup(
                "every component failed to refresh", list(report.failed.values())
            )

        for name in sorted(report.failed.keys() - self._failed):
            _LOGGER.warning(
                "%s: %s failed to refresh: %s", self.name, name, report.failed[name]
            )
        for name in sorted(self._failed - report.failed.keys()):
            _LOGGER.info("%s: %s is available again", self.name, name)
        self._failed = frozenset(report.failed)
        return report
