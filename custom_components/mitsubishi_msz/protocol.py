"""Codec for the Mitsubishi CN105 frames relayed by a MAC-559IF-E adapter.

The adapter proxies the indoor unit's native CN105 serial protocol over local
HTTP, handing back the raw frames as hex in its XML responses.  This module
turns those frames into state objects and builds the command frames that go
back the other way.

Frame layout (22 bytes)::

    0       0xFC start byte
    1       frame type: 0x62 / 0x7B response, 0x41 command
    2..4    0x01 0x30 0x10 (fixed header)
    5       segment / command group
    6..20   payload
    21      checksum

Field offsets below are absolute positions in the full frame.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

START_BYTE = 0xFC
HEADER = b"\x01\x30\x10"
FRAME_LEN = 22

TYPE_RESPONSE = 0x62
TYPE_PROFILE = 0x7B
TYPE_COMMAND = 0x41

SEG_GENERAL = 0x02
SEG_SENSOR = 0x03
SEG_ERROR = 0x04
SEG_TIMER = 0x05
SEG_ENERGY = 0x06
SEG_AUTO = 0x09

CMD_GENERAL = 0x01
CMD_EXTEND08 = 0x08

NO_ERROR = 0x8000

# A measured temperature of exactly -64 C is the protocol's "no sensor" marker.
# The MSZ-GL60VGD has no outdoor sensor on CN105 and reports raw 0x01
# (-63.5 C), so anything outside a plausible range is treated as missing too.
TEMP_MIN_PLAUSIBLE = -40.0
TEMP_MAX_PLAUSIBLE = 60.0


class ProtocolError(Exception):
    """A frame was malformed or failed its checksum."""


class Power(enum.IntEnum):
    OFF = 0
    ON = 1


class DriveMode(enum.IntEnum):
    AUTO = 0
    HEAT = 1
    DRY = 2
    COOL = 3
    FAN = 7


class FanSpeed(enum.IntEnum):
    AUTO = 0
    S1 = 1
    S2 = 2
    S3 = 3
    S4 = 5  # 4 is not used by the protocol
    FULL = 6


class VerticalVane(enum.IntEnum):
    AUTO = 0
    V1 = 1
    V2 = 2
    V3 = 3
    V4 = 4
    V5 = 5
    SWING = 7


class HorizontalVane(enum.IntEnum):
    AUTO = 0
    FAR_LEFT = 1
    LEFT = 2
    CENTER = 3
    RIGHT = 4
    FAR_RIGHT = 5
    LEFT_CENTER = 6
    CENTER_RIGHT = 7
    LEFT_RIGHT = 8
    LEFT_CENTER_RIGHT = 9
    SWING = 12


class RemoteLock(enum.IntFlag):
    UNLOCKED = 0
    POWER = 1
    MODE = 2
    TEMPERATURE = 4


class Controls(enum.IntFlag):
    """Which fields of a general command the unit should actually apply."""

    NONE = 0
    POWER = 0x0100
    DRIVE_MODE = 0x0200
    TEMPERATURE = 0x0400
    FAN_SPEED = 0x0800
    VERTICAL_VANE = 0x1000
    REMOTE_LOCK = 0x4000
    HORIZONTAL_VANE = 0x0001
    OUTSIDE_CONTROL = 0x0002


class Controls08(enum.IntFlag):
    """Field selector for the extended (0x08) command."""

    NONE = 0
    DEHUM = 0x04
    POWER_SAVING = 0x08
    BUZZER = 0x10
    WIND_BREAK = 0x20


def calc_checksum(payload: bytes) -> int:
    """Checksum over the frame excluding the start byte and the checksum."""
    return (0x100 - (sum(payload[0:20]) % 0x100)) % 0x100


def _decode_half_degree(raw: int) -> float | None:
    """Temperatures encoded as 0x80 + (celsius * 2)."""
    value = (raw - 0x80) * 0.5
    if value < TEMP_MIN_PLAUSIBLE or value > TEMP_MAX_PLAUSIBLE:
        return None
    return value


def _safe_enum(enum_class: type, value: int) -> Any:
    try:
        return enum_class(value)
    except ValueError:
        return value


def validate(frame: bytes) -> bytes:
    """Check a frame's shape and checksum, returning it unchanged."""
    if len(frame) != FRAME_LEN:
        raise ProtocolError(f"expected {FRAME_LEN} bytes, got {len(frame)}")
    if frame[0] != START_BYTE:
        raise ProtocolError(f"bad start byte 0x{frame[0]:02X}")
    expected = calc_checksum(frame[1:-1])
    if expected != frame[-1]:
        raise ProtocolError(
            f"checksum 0x{frame[-1]:02X}, expected 0x{expected:02X}"
        )
    return frame


@dataclass
class GeneralState:
    """Segment 0x02 - what the unit is set to do."""

    power: bool = False
    drive_mode: DriveMode | int = DriveMode.AUTO
    target_temp: float = 22.0
    fine_temp_supported: bool = True
    fan_speed: FanSpeed | int = FanSpeed.AUTO
    vertical_vane: VerticalVane | int = VerticalVane.AUTO
    horizontal_vane: HorizontalVane | int = HorizontalVane.AUTO
    remote_lock: RemoteLock | int = RemoteLock.UNLOCKED
    i_see_sensor: bool = False
    power_saving: bool = False
    dehum_setting: int = 0
    wind_break: int = 0

    @classmethod
    def parse(cls, f: bytes) -> "GeneralState":
        obj = cls()
        obj.power = bool(f[8])
        obj.drive_mode = _safe_enum(DriveMode, f[9] & 0x07)
        obj.i_see_sensor = bool(f[9] & 0x08)
        obj.fan_speed = _safe_enum(FanSpeed, f[11])
        obj.vertical_vane = _safe_enum(VerticalVane, f[12])
        obj.remote_lock = _safe_enum(RemoteLock, f[13])
        obj.horizontal_vane = _safe_enum(HorizontalVane, f[15] & 0x0F)
        if f[16]:
            obj.target_temp = (f[16] - 0x80) / 2
            obj.fine_temp_supported = True
        else:
            # Older boards only carry whole degrees, inverted around 31.
            obj.target_temp = float(31 - f[10])
            obj.fine_temp_supported = False
        obj.dehum_setting = f[17]
        obj.power_saving = f[18] > 0
        obj.wind_break = f[19]
        return obj

    def build_command(self, controls: Controls) -> bytes:
        """Build a 0x01 command frame carrying this state.

        Every field is populated from the current state and `controls` selects
        which ones the unit acts on, so an unrelated setting cannot be
        clobbered by a partially filled frame.
        """
        cmd = bytearray(b"\x41\x01\x30\x10\x01") + bytearray(15)
        controls |= Controls.OUTSIDE_CONTROL
        cmd[5] = (controls >> 8) & 0xFF
        cmd[6] = controls & 0xFF
        cmd[7] = int(self.power)
        cmd[8] = int(self.drive_mode)
        cmd[9] = 31 - int(self.target_temp)
        cmd[10] = int(self.fan_speed)
        cmd[11] = int(self.vertical_vane)
        cmd[15] = int(self.remote_lock)
        cmd[17] = int(self.horizontal_vane)
        cmd[18] = 0x80 + int(self.target_temp * 2)
        cmd[19] = 0x41
        return bytes([START_BYTE]) + bytes(cmd) + bytes([calc_checksum(cmd)])

    def build_extend_command(self, controls: Controls08) -> bytes:
        """Build a 0x08 command frame (power saving, buzzer, wind break)."""
        cmd = bytearray(b"\x41\x01\x30\x10\x08") + bytearray(15)
        cmd[5] = int(controls) & 0xFF
        cmd[8] = self.dehum_setting if controls & Controls08.DEHUM else 0
        cmd[9] = 0x0A if self.power_saving else 0x00
        cmd[10] = self.wind_break if controls & Controls08.WIND_BREAK else 0
        cmd[11] = 0x01 if controls & Controls08.BUZZER else 0x00
        return bytes([START_BYTE]) + bytes(cmd) + bytes([calc_checksum(cmd)])


@dataclass
class SensorState:
    """Segment 0x03 - what the unit measures."""

    room_temp: float | None = None
    room_temp_secondary: float | None = None
    outdoor_temp: float | None = None
    runtime_minutes: int = 0

    @classmethod
    def parse(cls, f: bytes) -> "SensorState":
        obj = cls()
        obj.outdoor_temp = _decode_half_degree(f[10])
        fine = _decode_half_degree(f[11])
        obj.room_temp = fine if fine is not None else float(10 + f[8])
        obj.room_temp_secondary = _decode_half_degree(f[12])
        obj.runtime_minutes = int.from_bytes(f[15:19], "big")
        return obj


@dataclass
class EnergyState:
    """Segment 0x06 - compressor activity and consumption."""

    operating: bool = False
    power_watt: int | None = None
    energy_kwh: float | None = None

    @classmethod
    def parse(cls, f: bytes) -> "EnergyState":
        obj = cls()
        obj.operating = bool(f[9])
        obj.power_watt = int.from_bytes(f[10:12], "big")
        # Reported in units of 100 Wh.
        obj.energy_kwh = int.from_bytes(f[12:14], "big") / 10
        return obj


@dataclass
class ErrorState:
    """Segment 0x04 - fault code, 0x8000 meaning healthy."""

    error_code: int = NO_ERROR

    @property
    def has_error(self) -> bool:
        return self.error_code != NO_ERROR

    @classmethod
    def parse(cls, f: bytes) -> "ErrorState":
        return cls(error_code=int.from_bytes(f[9:11], "big"))


@dataclass
class DeviceState:
    """Everything decoded from one poll of the adapter."""

    general: GeneralState = field(default_factory=GeneralState)
    sensor: SensorState = field(default_factory=SensorState)
    energy: EnergyState = field(default_factory=EnergyState)
    error: ErrorState = field(default_factory=ErrorState)
    mac: str | None = None
    serial: str | None = None
    rssi: int | None = None
    connected: bool = True
    snapshot_time: str | None = None
    raw_frames: list[str] = field(default_factory=list)


def parse_frames(hex_values: list[str]) -> dict[int, bytes]:
    """Validate a batch of hex frames and index them by segment."""
    segments: dict[int, bytes] = {}
    for value in hex_values:
        try:
            frame = validate(bytes.fromhex(value))
        except (ValueError, ProtocolError):
            continue
        if frame[1] not in (TYPE_RESPONSE, TYPE_PROFILE):
            continue
        segments[frame[5]] = frame
    return segments
