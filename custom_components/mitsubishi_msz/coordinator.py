"""Polling coordinator for one Mitsubishi indoor unit."""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiError, MitsubishiLocalApi
from .const import DOMAIN, WRITE_SETTLE_SECONDS
from .protocol import Controls, Controls08, DeviceState, GeneralState

_LOGGER = logging.getLogger(__name__)


class MszCoordinator(DataUpdateCoordinator[DeviceState]):
    """Keeps one unit's state fresh and funnels every write through one place."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: MitsubishiLocalApi,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {api.host}",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )
        self.api = api
        self.unit_info: dict[str, str] = {}
        self._cancel_settle: Callable[[], None] | None = None

    @property
    def host(self) -> str:
        return self.api.host

    async def async_load_unit_info(self) -> None:
        """Read the adapter's description; failure here is not fatal."""
        try:
            self.unit_info = await self.api.async_get_unit_info()
        except ApiError as err:
            _LOGGER.debug("Could not read /unitinfo from %s: %s", self.host, err)

    async def _async_update_data(self) -> DeviceState:
        try:
            return await self.api.async_get_state()
        except ApiError as err:
            raise UpdateFailed(str(err)) from err

    def _schedule_settle_refresh(self) -> None:
        """Re-poll once the adapter's cached snapshot has caught up."""
        if self._cancel_settle is not None:
            self._cancel_settle()

        async def _refresh(_now) -> None:
            self._cancel_settle = None
            await self.async_request_refresh()

        self._cancel_settle = async_call_later(
            self.hass, WRITE_SETTLE_SECONDS, _refresh
        )

    async def async_apply(
        self, controls: Controls, mutate: Callable[[GeneralState], None]
    ) -> None:
        """Change one or more settings on the indoor unit.

        The full current state is sent every time with `controls` naming the
        fields to act on, so a command cannot disturb an unrelated setting.
        The new value is shown straight away and confirmed by a later poll.
        """
        if self.data is None:
            raise UpdateFailed("No state has been read from the unit yet")

        general = copy.deepcopy(self.data.general)
        mutate(general)
        try:
            await self.api.async_send_frame(general.build_command(controls))
        except ApiError as err:
            raise UpdateFailed(f"Command to {self.host} failed: {err}") from err

        optimistic = copy.deepcopy(self.data)
        optimistic.general = general
        self.async_set_updated_data(optimistic)
        self._schedule_settle_refresh()

    async def async_apply_extended(
        self, controls: Controls08, mutate: Callable[[GeneralState], None]
    ) -> None:
        """Change a setting carried by the extended (0x08) command."""
        if self.data is None:
            raise UpdateFailed("No state has been read from the unit yet")

        general = copy.deepcopy(self.data.general)
        mutate(general)
        try:
            await self.api.async_send_frame(general.build_extend_command(controls))
        except ApiError as err:
            raise UpdateFailed(f"Command to {self.host} failed: {err}") from err

        optimistic = copy.deepcopy(self.data)
        optimistic.general = general
        self.async_set_updated_data(optimistic)
        self._schedule_settle_refresh()

    async def async_shutdown(self) -> None:
        if self._cancel_settle is not None:
            self._cancel_settle()
            self._cancel_settle = None
        await super().async_shutdown()
