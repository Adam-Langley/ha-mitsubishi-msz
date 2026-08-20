"""Diagnostics dump - decoded state plus the raw frames behind it."""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import MszCoordinator

TO_REDACT = {"mac", "serial", "serial_number", CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: MszCoordinator = entry.runtime_data
    state = coordinator.data

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "unit_info": async_redact_data(dict(coordinator.unit_info), TO_REDACT),
        "state": async_redact_data(
            dataclasses.asdict(state) if state else {}, TO_REDACT
        ),
    }
