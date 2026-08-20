"""Switches for the extended settings the unit exposes."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MszCoordinator
from .entity import MszEntity
from .protocol import Controls08, GeneralState


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([MszPowerSavingSwitch(entry.runtime_data)])


class MszPowerSavingSwitch(MszEntity, SwitchEntity):
    """Economy / power saving mode, carried by the 0x08 command."""

    _attr_translation_key = "power_saving"

    def __init__(self, coordinator: MszCoordinator) -> None:
        super().__init__(coordinator, "power_saving")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.general.power_saving

    async def _async_set(self, enabled: bool) -> None:
        def mutate(general: GeneralState) -> None:
            general.power_saving = enabled

        await self.coordinator.async_apply_extended(
            Controls08.POWER_SAVING, mutate
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)
