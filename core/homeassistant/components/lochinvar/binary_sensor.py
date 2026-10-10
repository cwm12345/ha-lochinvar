"""Binary sensors for Lochinvar boilers."""

# Written by Claude, guided by Chris.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lochinvar_modbus import DiscreteInputs, LochinvarBoiler

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LochinvarConfigEntry
from .entity import LochinvarEntity, LochinvarEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LochinvarBinarySensorDescription(
    BinarySensorEntityDescription, LochinvarEntityDescription
):
    """Describe a Lochinvar binary sensor."""

    value_fn: Callable[[LochinvarBoiler], bool | None]


def _input(
    key: str,
    which: DiscreteInputs,
    *,
    device_class: BinarySensorDeviceClass | None = None,
    entity_category: EntityCategory | None = None,
) -> LochinvarBinarySensorDescription:
    """Describe a discrete input.

    The manual gives only ON/OFF, not what ON means for a safety switch, so
    those carry no device class.
    """
    return LochinvarBinarySensorDescription(
        key=key,
        translation_key=key,
        component="status",
        device_class=device_class,
        entity_category=entity_category,
        value_fn=lambda d: d.status.input_on(which),
    )


_RUNNING = BinarySensorDeviceClass.RUNNING
_DIAGNOSTIC = EntityCategory.DIAGNOSTIC

BINARY_SENSOR_DESCRIPTIONS: tuple[LochinvarBinarySensorDescription, ...] = (
    _input("flame", DiscreteInputs.FLAME),
    _input("gas_valve", DiscreteInputs.GAS_VALVE),
    _input("ch_pump", DiscreteInputs.CH_PUMP, device_class=_RUNNING),
    _input("dhw_pump", DiscreteInputs.DHW_PUMP, device_class=_RUNNING),
    _input("system_pump", DiscreteInputs.SYSTEM_PUMP, device_class=_RUNNING),
    _input(
        "dhw_recirculation_pump",
        DiscreteInputs.DHW_RECIRCULATION_PUMP,
        device_class=_RUNNING,
    ),
    _input(
        "room_thermostat_1_demand",
        DiscreteInputs.ROOM_THERMOSTAT_1,
        entity_category=_DIAGNOSTIC,
    ),
    _input(
        "room_thermostat_2_demand",
        DiscreteInputs.ROOM_THERMOSTAT_2,
        entity_category=_DIAGNOSTIC,
    ),
    _input(
        "tank_thermostat_demand",
        DiscreteInputs.TANK_THERMOSTAT,
        entity_category=_DIAGNOSTIC,
    ),
    _input("flow_switch", DiscreteInputs.FLOW_SWITCH),
    _input("gas_pressure_switch", DiscreteInputs.GAS_PRESSURE_SWITCH),
    _input("air_pressure_switch", DiscreteInputs.AIR_PRESSURE_SWITCH),
    _input("blocked_drain_switch", DiscreteInputs.BLOCKED_DRAIN_SWITCH),
    _input("auto_reset_high_limit", DiscreteInputs.AUTO_RESET_HIGH_LIMIT),
    _input("louver_proving_switch", DiscreteInputs.LOUVER_PROVING_SWITCH),
    _input("louver_relay", DiscreteInputs.LOUVER_RELAY),
    _input("alarm_contacts", DiscreteInputs.ALARM_CONTACTS),
    _input(
        "run_time_contacts",
        DiscreteInputs.RUN_TIME_CONTACTS,
        entity_category=_DIAGNOSTIC,
    ),
    LochinvarBinarySensorDescription(
        key="lockout",
        translation_key="lockout",
        component="status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.status.locked_out,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LochinvarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lochinvar binary sensors."""
    async_add_entities(
        LochinvarBinarySensor(entry, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class LochinvarBinarySensor(LochinvarEntity, BinarySensorEntity):
    """A boiler on/off state."""

    entity_description: LochinvarBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """The state from the latest poll."""
        return self.entity_description.value_fn(self.coordinator.device)
