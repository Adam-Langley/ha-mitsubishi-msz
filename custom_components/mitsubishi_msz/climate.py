"""The indoor unit as a Home Assistant climate entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DRIVE_TO_HVAC_MODE,
    FAN_MODE_TO_SPEED,
    HVAC_MODE_TO_DRIVE,
    MAX_TEMP,
    MIN_TEMP,
    SPEED_TO_FAN_MODE,
    SWING_MODE_TO_VANE,
    TEMP_STEP,
    VANE_TO_SWING_MODE,
)
from .coordinator import MszCoordinator
from .entity import MszEntity
from .protocol import Controls, DriveMode, GeneralState

ACTION_BY_MODE: dict[DriveMode, HVACAction] = {
    DriveMode.HEAT: HVACAction.HEATING,
    DriveMode.COOL: HVACAction.COOLING,
    DriveMode.DRY: HVACAction.DRYING,
    DriveMode.FAN: HVACAction.FAN,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([MszClimate(entry.runtime_data)])


class MszClimate(MszEntity, ClimateEntity):
    """Power, mode, setpoint, fan and vane for one indoor unit."""

    _attr_name = None
    _attr_translation_key = "heat_pump"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = TEMP_STEP
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_fan_modes = list(FAN_MODE_TO_SPEED)
    _attr_swing_modes = list(SWING_MODE_TO_VANE)
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: MszCoordinator) -> None:
        super().__init__(coordinator, "climate")

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.data.sensor.room_temp

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.data.general.target_temp

    @property
    def hvac_mode(self) -> HVACMode:
        general = self.coordinator.data.general
        if not general.power:
            return HVACMode.OFF
        if isinstance(general.drive_mode, DriveMode):
            return DRIVE_TO_HVAC_MODE.get(general.drive_mode, HVACMode.HEAT_COOL)
        return HVACMode.HEAT_COOL

    @property
    def hvac_action(self) -> HVACAction | None:
        data = self.coordinator.data
        if not data.general.power:
            return HVACAction.OFF
        if not data.energy.operating:
            return HVACAction.IDLE
        if isinstance(data.general.drive_mode, DriveMode):
            if data.general.drive_mode is DriveMode.AUTO:
                # In auto the unit picks a direction; infer it from the room.
                room = data.sensor.room_temp
                target = data.general.target_temp
                if room is not None:
                    return (
                        HVACAction.HEATING if room < target else HVACAction.COOLING
                    )
                return None
            return ACTION_BY_MODE.get(data.general.drive_mode)
        return None

    @property
    def fan_mode(self) -> str | None:
        return SPEED_TO_FAN_MODE.get(self.coordinator.data.general.fan_speed)

    @property
    def swing_mode(self) -> str | None:
        return VANE_TO_SWING_MODE.get(self.coordinator.data.general.vertical_vane)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        clamped = min(max(float(temperature), MIN_TEMP), MAX_TEMP)
        # The wire format carries half degrees, so snap to the nearest 0.5.
        clamped = round(clamped * 2) / 2

        def mutate(general: GeneralState) -> None:
            general.target_temp = clamped

        await self.coordinator.async_apply(Controls.TEMPERATURE, mutate)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return

        drive = HVAC_MODE_TO_DRIVE[hvac_mode]

        def mutate(general: GeneralState) -> None:
            general.power = True
            general.drive_mode = drive

        # Switching mode while off should also switch the unit on.
        await self.coordinator.async_apply(
            Controls.POWER | Controls.DRIVE_MODE, mutate
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        speed = FAN_MODE_TO_SPEED[fan_mode]

        def mutate(general: GeneralState) -> None:
            general.fan_speed = speed

        await self.coordinator.async_apply(Controls.FAN_SPEED, mutate)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        vane = SWING_MODE_TO_VANE[swing_mode]

        def mutate(general: GeneralState) -> None:
            general.vertical_vane = vane

        await self.coordinator.async_apply(Controls.VERTICAL_VANE, mutate)

    async def async_turn_on(self) -> None:
        def mutate(general: GeneralState) -> None:
            general.power = True

        await self.coordinator.async_apply(Controls.POWER, mutate)

    async def async_turn_off(self) -> None:
        def mutate(general: GeneralState) -> None:
            general.power = False

        await self.coordinator.async_apply(Controls.POWER, mutate)
