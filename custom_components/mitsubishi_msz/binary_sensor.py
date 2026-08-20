"""Binary sensors for compressor activity and fault reporting."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import MszCoordinator
from .entity import MszEntity
from .protocol import DeviceState


@dataclass(frozen=True, kw_only=True)
class MszBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[DeviceState], bool]


BINARY_SENSORS: tuple[MszBinarySensorDescription, ...] = (
    MszBinarySensorDescription(
        key="operating",
        translation_key="operating",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda state: state.energy.operating,
    ),
    MszBinarySensorDescription(
        key="problem",
        translation_key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.error.has_error,
    ),
    MszBinarySensorDescription(
        key="i_see_sensor",
        translation_key="i_see_sensor",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.general.i_see_sensor,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MszCoordinator = entry.runtime_data
    async_add_entities(
        MszBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class MszBinarySensor(MszEntity, BinarySensorEntity):
    entity_description: MszBinarySensorDescription

    def __init__(
        self, coordinator: MszCoordinator, description: MszBinarySensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data)
