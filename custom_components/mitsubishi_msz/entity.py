"""Shared base class for every entity this integration creates."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import MszCoordinator


class MszEntity(CoordinatorEntity[MszCoordinator]):
    """Ties an entity to the indoor unit it belongs to."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MszCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        info = self.coordinator.unit_info
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.unique_id or self.coordinator.host)},
            manufacturer=MANUFACTURER,
            name=self.coordinator.config_entry.title,
            model=info.get("model", "MAC-559IF-E"),
            serial_number=info.get("serial"),
            sw_version=info.get("m16cromver"),
            configuration_url=f"http://{self.coordinator.host}/unitinfo",
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None
