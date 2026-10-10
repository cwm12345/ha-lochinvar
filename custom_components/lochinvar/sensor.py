"""Sensors for Lochinvar boilers."""

# Written by Claude, guided by Chris.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import LochinvarConfigEntry
from .entity import LochinvarEntity, LochinvarEntityDescription
from .lochinvar_modbus import (
    BlockingCode,
    LochinvarBoiler,
    LockoutCode,
    StatusCode,
    TemperatureUnit,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LochinvarSensorDescription(SensorEntityDescription, LochinvarEntityDescription):
    """Describe a Lochinvar sensor."""

    value_fn: Callable[[LochinvarBoiler], StateType]
    exists_fn: Callable[[LochinvarBoiler], bool] = lambda _: True
    temperature: bool = False
    """Native unit is the boiler's temperature unit, set per config entry."""


def _temperature(
    key: str,
    component: str,
    value_fn: Callable[[LochinvarBoiler], StateType],
    *,
    exists_fn: Callable[[LochinvarBoiler], bool] = lambda _: True,
    entity_category: EntityCategory | None = None,
) -> LochinvarSensorDescription:
    return LochinvarSensorDescription(
        key=key,
        translation_key=key,
        component=component,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        temperature=True,
        entity_category=entity_category,
        value_fn=value_fn,
        exists_fn=exists_fn,
    )


def _percent(
    key: str,
    value_fn: Callable[[LochinvarBoiler], StateType],
    *,
    exists_fn: Callable[[LochinvarBoiler], bool] = lambda _: True,
    component: str = "status",
    entity_category: EntityCategory | None = None,
) -> LochinvarSensorDescription:
    return LochinvarSensorDescription(
        key=key,
        translation_key=key,
        component=component,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=entity_category,
        value_fn=value_fn,
        exists_fn=exists_fn,
    )


def _raw(
    key: str, component: str, value_fn: Callable[[LochinvarBoiler], StateType]
) -> LochinvarSensorDescription:
    """Describe a raw code or bit word, for diagnostics."""
    return LochinvarSensorDescription(
        key=key,
        translation_key=key,
        component=component,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=value_fn,
    )


def _enum[E: IntEnum](
    key: str, table: type[E], value_fn: Callable[[LochinvarBoiler], E | int | None]
) -> LochinvarSensorDescription:
    """Describe a decoded code; one the manual doesn't list reads unknown."""

    def value(device: LochinvarBoiler) -> str | None:
        code = value_fn(device)
        return code.name.lower() if isinstance(code, table) else None

    return LochinvarSensorDescription(
        key=key,
        translation_key=key,
        component="status",
        device_class=SensorDeviceClass.ENUM,
        options=[member.name.lower() for member in table],
        value_fn=value,
    )


def _has_system_sensor(device: LochinvarBoiler) -> bool:
    return device.bms.system_supply_temperature is not None


def _in_cascade(device: LochinvarBoiler) -> bool:
    return bool(device.status.cascade_total_power)


# Keys are part of each entity's unique ID; keep them stable.
SENSOR_DESCRIPTIONS: tuple[LochinvarSensorDescription, ...] = (
    _temperature("outlet_temperature", "status", lambda d: d.status.outlet_temperature),
    _temperature("inlet_temperature", "status", lambda d: d.status.inlet_temperature),
    _temperature("flue_temperature", "status", lambda d: d.status.flue_temperature),
    _temperature("outlet_setpoint", "status", lambda d: d.status.outlet_setpoint),
    _temperature("tank_temperature", "bms", lambda d: d.bms.tank_temperature),
    _temperature("tank_setpoint", "bms", lambda d: d.bms.tank_setpoint),
    _temperature("outdoor_temperature", "bms", lambda d: d.bms.outdoor_temperature),
    # Sensors a boiler may not have: created only when one is connected.
    _temperature(
        "system_supply_temperature",
        "bms",
        lambda d: d.bms.system_supply_temperature,
        exists_fn=_has_system_sensor,
    ),
    _temperature(
        "system_setpoint",
        "status",
        lambda d: d.status.system_setpoint,
        exists_fn=_has_system_sensor,
    ),
    _temperature(
        "dhw_recirculation_temperature",
        "bms",
        lambda d: d.bms.dhw_recirculation_temperature,
        exists_fn=lambda d: d.bms.dhw_recirculation_temperature is not None,
    ),
    _percent("firing_rate", lambda d: d.status.firing_rate),
    _percent("pump_speed", lambda d: d.status.boiler_pump_speed),
    _percent("system_pump_speed", lambda d: d.status.system_pump_speed),
    _percent(
        "cascade_total_power",
        lambda d: d.status.cascade_total_power,
        exists_fn=_in_cascade,
    ),
    _percent(
        "cascade_current_power",
        lambda d: d.status.cascade_current_power,
        exists_fn=_in_cascade,
    ),
    _enum("status", StatusCode, lambda d: d.status.status),
    _enum("blocking", BlockingCode, lambda d: d.status.blocking),
    _enum("lockout_reason", LockoutCode, lambda d: d.status.lockout),
    _raw("status_code", "status", lambda d: d.status.status_code),
    _raw("blocking_code", "status", lambda d: d.status.blocking_code),
    _raw("lockout_code", "status", lambda d: d.status.lockout_code),
    _raw("bms_configuration", "bms", lambda d: d.bms.configuration),
    _raw("bms_command", "bms", lambda d: d.bms.command),
    _percent(
        "rate_command",
        lambda d: d.bms.rate_command,
        component="bms",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LochinvarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lochinvar sensors."""
    device = entry.runtime_data.device
    async_add_entities(
        LochinvarSensor(entry, description)
        for description in SENSOR_DESCRIPTIONS
        if description.exists_fn(device)
    )


class LochinvarSensor(LochinvarEntity, SensorEntity):
    """A boiler reading."""

    entity_description: LochinvarSensorDescription

    def __init__(
        self, entry: LochinvarConfigEntry, description: LochinvarSensorDescription
    ) -> None:
        """Initialize the sensor, in the boiler's temperature unit if it has one."""
        super().__init__(entry, description)
        if description.temperature:
            self._attr_native_unit_of_measurement = (
                UnitOfTemperature.FAHRENHEIT
                if entry.runtime_data.device.temperature_unit
                is TemperatureUnit.FAHRENHEIT
                else UnitOfTemperature.CELSIUS
            )

    @property
    def native_value(self) -> StateType:
        """The value from the latest poll."""
        return self.entity_description.value_fn(self.coordinator.device)
