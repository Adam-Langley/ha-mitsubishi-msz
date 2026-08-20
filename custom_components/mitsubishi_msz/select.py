"""Horizontal vane position, which the climate entity has no slot for."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import HORIZONTAL_VANE_OPTIONS, VANE_TO_HORIZONTAL_OPTION
from .coordinator import MszCoordinator
from .entity import MszEntity
from .protocol import Controls, GeneralState


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([MszHorizontalVane(entry.runtime_data)])


class MszHorizontalVane(MszEntity, SelectEntity):
    """Left/right louvre position.

    Not every model has a motorised horizontal louvre - on those the unit
    simply ignores the command and keeps reporting its fixed position.
    """

    _attr_translation_key = "horizontal_vane"
    _attr_options = list(HORIZONTAL_VANE_OPTIONS)

    def __init__(self, coordinator: MszCoordinator) -> None:
        super().__init__(coordinator, "horizontal_vane")

    @property
    def current_option(self) -> str | None:
        return VANE_TO_HORIZONTAL_OPTION.get(
            self.coordinator.data.general.horizontal_vane
        )

    async def async_select_option(self, option: str) -> None:
        vane = HORIZONTAL_VANE_OPTIONS[option]

        def mutate(general: GeneralState) -> None:
            general.horizontal_vane = vane

        await self.coordinator.async_apply(Controls.HORIZONTAL_VANE, mutate)
