"""Polling coordinator for one Mitsubishi indoor unit."""

from __future__ import annotations

import copy
import dataclasses
import logging
from collections.abc import Callable
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiError, MitsubishiLocalApi
from .const import CONFIRM_WINDOW_SECONDS, DOMAIN, REFRESH_DELAYS
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
        self._cancels: list[Callable[[], None]] = []
        # Fields we have commanded but the unit has not yet echoed back.
        self._pending_fields: set[str] = set()
        self._pending_state: GeneralState | None = None
        self._pending_until: float = 0.0

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
            state = await self.api.async_get_state()
        except ApiError as err:
            raise UpdateFailed(str(err)) from err
        self._reconcile(state)
        return state

    def _reconcile(self, state: DeviceState) -> None:
        """Hold a commanded value until the unit actually reports it back.

        The adapter serves a snapshot it refreshes on its own schedule, so a
        poll taken seconds after a command still describes the old state.
        Without this the UI would visibly snap back to the previous value
        before the next poll corrected it again.
        """
        if not self._pending_fields or self._pending_state is None:
            return

        if self.hass.loop.time() > self._pending_until:
            _LOGGER.debug(
                "%s never confirmed %s; accepting what the unit reports",
                self.host,
                sorted(self._pending_fields),
            )
            self._clear_pending()
            return

        outstanding: set[str] = set()
        for name in self._pending_fields:
            expected = getattr(self._pending_state, name)
            if getattr(state.general, name) != expected:
                setattr(state.general, name, expected)
                outstanding.add(name)

        if not outstanding:
            _LOGGER.debug("%s confirmed every commanded field", self.host)
            self._clear_pending()
        else:
            self._pending_fields = outstanding

    def _clear_pending(self) -> None:
        self._pending_fields = set()
        self._pending_state = None

    def _remember_pending(self, before: GeneralState, after: GeneralState) -> None:
        changed = {
            field.name
            for field in dataclasses.fields(GeneralState)
            if getattr(before, field.name) != getattr(after, field.name)
        }
        if not changed:
            return
        self._pending_fields |= changed
        self._pending_state = copy.deepcopy(after)
        self._pending_until = self.hass.loop.time() + CONFIRM_WINDOW_SECONDS

    def _schedule_confirmation_polls(self) -> None:
        """Re-poll a few times so a change is confirmed without a long wait."""
        self._cancel_scheduled()

        def make(delay: float) -> None:
            async def _refresh(_now) -> None:
                await self.async_request_refresh()

            self._cancels.append(async_call_later(self.hass, delay, _refresh))

        for delay in REFRESH_DELAYS:
            make(delay)

    def _cancel_scheduled(self) -> None:
        for cancel in self._cancels:
            cancel()
        self._cancels = []

    async def _async_send(
        self,
        mutate: Callable[[GeneralState], None],
        build: Callable[[GeneralState], bytes],
    ) -> None:
        if self.data is None:
            raise UpdateFailed("No state has been read from the unit yet")

        before = self.data.general
        general = copy.deepcopy(before)
        mutate(general)
        try:
            await self.api.async_send_frame(build(general))
        except ApiError as err:
            raise UpdateFailed(f"Command to {self.host} failed: {err}") from err

        self._remember_pending(before, general)

        optimistic = copy.deepcopy(self.data)
        optimistic.general = general
        self.async_set_updated_data(optimistic)
        self._schedule_confirmation_polls()

    async def async_apply(
        self, controls: Controls, mutate: Callable[[GeneralState], None]
    ) -> None:
        """Change one or more settings on the indoor unit.

        The full current state is sent every time with `controls` naming the
        fields to act on, so a command cannot disturb an unrelated setting.
        """
        await self._async_send(mutate, lambda state: state.build_command(controls))

    async def async_apply_extended(
        self, controls: Controls08, mutate: Callable[[GeneralState], None]
    ) -> None:
        """Change a setting carried by the extended (0x08) command."""
        await self._async_send(
            mutate, lambda state: state.build_extend_command(controls)
        )

    async def async_shutdown(self) -> None:
        self._cancel_scheduled()
        await super().async_shutdown()
