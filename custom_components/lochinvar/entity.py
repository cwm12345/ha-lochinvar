"""Base entity for Lochinvar boilers."""

# Written by Claude, guided by Chris.

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import LochinvarConfigEntry, LochinvarCoordinator


@dataclass(frozen=True, kw_only=True)
class LochinvarEntityDescription(EntityDescription):
    """Describe a Lochinvar entity."""

    component: str
    """The register table on LochinvarBoiler this entity reads from."""


class LochinvarEntity(CoordinatorEntity[LochinvarCoordinator]):
    """An entity on one boiler, reading one of its register tables."""

    _attr_has_entity_name = True
    entity_description: LochinvarEntityDescription

    def __init__(
        self, entry: LochinvarConfigEntry, description: LochinvarEntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(entry.runtime_data)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = self.coordinator.device_info

    @property
    def available(self) -> bool:
        """Whether this entity's register table answered the latest poll."""
        return (
            super().available
            and self.entity_description.component not in self.coordinator.data.failed
        )
