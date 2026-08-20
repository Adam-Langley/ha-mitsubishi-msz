"""Config flow: find the adapter and confirm it answers."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .api import ApiError, MitsubishiLocalApi
from .const import (
    CONF_SCAN_INTERVAL_SECONDS,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class MszConfigFlow(ConfigFlow, domain=DOMAIN):
    """Walk the user through adding one indoor unit."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._mac: str | None = None
        self._model: str | None = None

    async def _async_probe(self, host: str) -> tuple[str, str]:
        """Confirm the adapter is really there; return its MAC and model."""
        api = MitsubishiLocalApi(host, async_get_clientsession(self.hass))
        state = await api.async_get_state()
        info = await api.async_get_unit_info()
        mac = state.mac or info.get("mac")
        if not mac:
            raise ApiError("the adapter did not report a MAC address")
        return format_mac(mac), info.get("model", "MAC-559IF-E")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                mac, model = await self._async_probe(host)
            except ApiError as err:
                _LOGGER.debug("Probe of %s failed: %s", host, err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                    data={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host or ""): str,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Pick up an adapter that just appeared on the network.

        These adapters use a GainSpan Wi-Fi module and announce themselves with
        a `gainspan_*` hostname, but plenty of other GainSpan hardware exists,
        so the candidate is only accepted once it answers the local API.
        """
        host = discovery_info.ip
        try:
            mac, model = await self._async_probe(host)
        except ApiError:
            return self.async_abort(reason="not_mitsubishi")

        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._host = host
        self._model = model
        self.context["title_placeholders"] = {"name": f"{DEFAULT_NAME} ({host})"}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                data={CONF_HOST: self._host},
            )
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {vol.Optional(CONF_NAME, default=DEFAULT_NAME): str}
            ),
            description_placeholders={
                "host": self._host or "",
                "model": self._model or "",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MszOptionsFlow()


class MszOptionsFlow(OptionsFlow):
    """Lets the poll interval be tuned after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL_SECONDS, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL_SECONDS, default=current
                    ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL, max=600))
                }
            ),
        )
