"""Local HTTP client for a Mitsubishi MAC-559IF-E Wi-Fi adapter.

The adapter serves two unauthenticated endpoints on port 80:

``/smart``
    Accepts an XML ``<CSV>`` document and answers with an ``<LSV>`` document
    holding the indoor unit's CN105 frames as hex.  Posting a ``<CODE><VALUE>``
    element passes a command frame straight through to the unit.

``/unitinfo``
    A flat XML summary of the adapter itself - model, serial, signal strength.

Everything happens on the local network; the Mitsubishi cloud is not involved.
"""

from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET

import aiohttp

from .protocol import (
    DeviceState,
    EnergyState,
    ErrorState,
    GeneralState,
    ProtocolError,
    SEG_ENERGY,
    SEG_ERROR,
    SEG_GENERAL,
    SEG_SENSOR,
    SensorState,
    parse_frames,
)

_LOGGER = logging.getLogger(__name__)

STATUS_BODY = '<?xml version="1.0" encoding="UTF-8"?><CSV><CONNECT>ON</CONNECT></CSV>'
COMMAND_BODY = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<CSV><CONNECT>ON</CONNECT><CODE><VALUE>{frame}</VALUE></CODE></CSV>"
)
HEADERS = {
    "Content-Type": "text/plain;charset=UTF-8",
    "Connection": "close",
    "Accept": "*/*",
}

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=12, connect=5)
MAX_ATTEMPTS = 3
RETRY_DELAY = 1.0


class ApiError(Exception):
    """The adapter could not be reached or gave an unusable answer."""


class MitsubishiLocalApi:
    """Talks to one adapter over plain local HTTP."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self._host = host
        self._session = session
        # The adapter drops overlapping requests, so serialise them.
        self._lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self._host

    async def _post(self, body: str) -> str:
        url = f"http://{self._host}/smart"
        last: Exception | None = None
        async with self._lock:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    async with self._session.post(
                        url, data=body.encode(), headers=HEADERS, timeout=REQUEST_TIMEOUT
                    ) as response:
                        response.raise_for_status()
                        return await response.text()
                except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                    last = err
                    _LOGGER.debug(
                        "POST to %s failed (attempt %s/%s): %s",
                        self._host, attempt, MAX_ATTEMPTS, err,
                    )
                    if attempt < MAX_ATTEMPTS:
                        await asyncio.sleep(RETRY_DELAY)
        raise ApiError(f"{self._host} is not responding: {last}") from last

    async def async_get_state(self) -> DeviceState:
        """Poll the adapter and decode the indoor unit's current state."""
        text = await self._post(STATUS_BODY)
        try:
            root = ET.fromstring(text)
        except ET.ParseError as err:
            raise ApiError(f"{self._host} returned unparseable XML: {err}") from err

        values = [node.text or "" for node in root.iter("VALUE")]
        if not values:
            raise ApiError(f"{self._host} returned no CN105 frames")

        try:
            segments = parse_frames(values)
        except ProtocolError as err:
            raise ApiError(f"{self._host} sent a bad frame: {err}") from err

        if SEG_GENERAL not in segments:
            raise ApiError(f"{self._host} did not report the unit's settings")

        state = DeviceState(raw_frames=values)
        state.general = GeneralState.parse(segments[SEG_GENERAL])
        if SEG_SENSOR in segments:
            state.sensor = SensorState.parse(segments[SEG_SENSOR])
        if SEG_ENERGY in segments:
            state.energy = EnergyState.parse(segments[SEG_ENERGY])
        if SEG_ERROR in segments:
            state.error = ErrorState.parse(segments[SEG_ERROR])

        state.mac = _text(root, "MAC")
        state.serial = _text(root, "SERIAL")
        state.snapshot_time = _text(root, "DATDATE")
        state.connected = (_text(root, "CONNECT") or "ON").upper() == "ON"
        if (rssi := _text(root, "RSSI")) is not None:
            try:
                state.rssi = int(rssi)
            except ValueError:
                state.rssi = None
        return state

    async def async_send_frame(self, frame: bytes) -> None:
        """Pass a CN105 command frame through to the indoor unit."""
        _LOGGER.debug("Sending frame to %s: %s", self._host, frame.hex())
        await self._post(COMMAND_BODY.format(frame=frame.hex()))

    async def async_get_unit_info(self) -> dict[str, str]:
        """Read the adapter's own description from /unitinfo.

        The document declares Shift_JIS but only ever carries ASCII, so the
        flat tags are pulled out directly rather than through a parser that
        would need the codec.
        """
        url = f"http://{self._host}/unitinfo"
        try:
            async with self._session.get(url, timeout=REQUEST_TIMEOUT) as response:
                response.raise_for_status()
                text = await response.text(errors="ignore")
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ApiError(f"{self._host} /unitinfo unreachable: {err}") from err
        return {
            key: value
            for key, value in re.findall(r"<(\w+)>([^<>]*)</\1>", text)
            if key != "root"
        }


def _text(root: ET.Element, tag: str) -> str | None:
    node = root.find(tag)
    if node is None or node.text is None:
        return None
    return node.text.strip() or None
