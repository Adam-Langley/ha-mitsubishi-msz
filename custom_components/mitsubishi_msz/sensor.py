"""Sensors read from the indoor unit and its adapter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MszCoordinator
from .entity import MszEntity
from .protocol import DeviceState


@dataclass(frozen=True, kw_only=True)
class MszSensorDescription(SensorEntityDescription):
    """Describes one sensor and how to pull its value out of the state."""

    value_fn: Callable[[DeviceState], float | int | str | None]


SENSORS: tuple[MszSensorDescription, ...] = (
    MszSensorDescription(
        key="room_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda state: state.sensor.room_temp,
    ),
    MszSensorDescription(
        key="room_temperature_secondary",
        translation_key="room_temperature_secondary",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.sensor.room_temp_secondary,
    ),
    MszSensorDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda state: state.sensor.outdoor_temp,
    ),
    MszSensorDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda state: state.energy.power_watt,
    ),
    MszSensorDescription(
        key="energy",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda state: state.energy.energy_kwh,
    ),
    MszSensorDescription(
        key="runtime",
        translation_key="runtime",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.sensor.runtime_minutes,
    ),
    MszSensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.rssi,
    ),
    MszSensorDescription(
        key="error_code",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: f"0x{state.error.error_code:04X}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator: MszCoordinator = entry.runtime_data
    state = coordinator.data

    entities = []
    for description in SENSORS:
        # This model has no outdoor sensor wired to CN105; skip the entity
        # rather than leave one permanently unknown.
        if description.key == "outdoor_temperature" and state.sensor.outdoor_temp is None:
            continue
        entities.append(MszSensor(coordinator, description))
    async_add_entities(entities)


class MszSensor(MszEntity, SensorEntity):
    """One value read from the unit."""

    entity_description: MszSensorDescription

    def __init__(
        self, coordinator: MszCoordinator, description: MszSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | None:
        return self.entity_description.value_fn(self.coordinator.data)
