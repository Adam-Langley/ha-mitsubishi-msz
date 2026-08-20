"""Constants and Home Assistant value mappings."""

from __future__ import annotations

from homeassistant.components.climate import HVACMode

from .protocol import DriveMode, FanSpeed, HorizontalVane, VerticalVane

DOMAIN = "mitsubishi_msz"
MANUFACTURER = "Mitsubishi Electric"
DEFAULT_NAME = "Heat Pump"

CONF_SCAN_INTERVAL_SECONDS = "scan_interval_seconds"
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10

# The adapter serves a snapshot of the indoor unit that it refreshes on its
# own schedule.  Measured propagation of a command was around 12 seconds, so
# poll a few times afterwards rather than once, and keep showing the commanded
# value until the unit echoes it back or the window expires.
REFRESH_DELAYS = (5, 10, 16, 24)
CONFIRM_WINDOW_SECONDS = 30

MIN_TEMP = 16.0
MAX_TEMP = 31.0
TEMP_STEP = 0.5

# The unit's mode 0x00 is the remote's AUTO, where the unit itself decides
# whether to heat or cool from a single setpoint.  That is HVACMode.AUTO
# rather than HEAT_COOL, which implies a two-ended target range.
HVAC_MODE_TO_DRIVE: dict[HVACMode, DriveMode] = {
    HVACMode.AUTO: DriveMode.AUTO,
    HVACMode.HEAT: DriveMode.HEAT,
    HVACMode.DRY: DriveMode.DRY,
    HVACMode.COOL: DriveMode.COOL,
    HVACMode.FAN_ONLY: DriveMode.FAN,
}
DRIVE_TO_HVAC_MODE: dict[DriveMode, HVACMode] = {
    v: k for k, v in HVAC_MODE_TO_DRIVE.items()
}

FAN_MODE_TO_SPEED: dict[str, FanSpeed] = {
    "auto": FanSpeed.AUTO,
    "quiet": FanSpeed.S1,
    "low": FanSpeed.S2,
    "medium": FanSpeed.S3,
    "high": FanSpeed.S4,
    "max": FanSpeed.FULL,
}
SPEED_TO_FAN_MODE: dict[FanSpeed, str] = {v: k for k, v in FAN_MODE_TO_SPEED.items()}

# The vertical vane doubles as Home Assistant's swing control.
SWING_MODE_TO_VANE: dict[str, VerticalVane] = {
    "auto": VerticalVane.AUTO,
    "position_1": VerticalVane.V1,
    "position_2": VerticalVane.V2,
    "position_3": VerticalVane.V3,
    "position_4": VerticalVane.V4,
    "position_5": VerticalVane.V5,
    "swing": VerticalVane.SWING,
}
VANE_TO_SWING_MODE: dict[VerticalVane, str] = {
    v: k for k, v in SWING_MODE_TO_VANE.items()
}

HORIZONTAL_VANE_OPTIONS: dict[str, HorizontalVane] = {
    "auto": HorizontalVane.AUTO,
    "far_left": HorizontalVane.FAR_LEFT,
    "left": HorizontalVane.LEFT,
    "center": HorizontalVane.CENTER,
    "right": HorizontalVane.RIGHT,
    "far_right": HorizontalVane.FAR_RIGHT,
    "left_center": HorizontalVane.LEFT_CENTER,
    "center_right": HorizontalVane.CENTER_RIGHT,
    "left_right": HorizontalVane.LEFT_RIGHT,
    "left_center_right": HorizontalVane.LEFT_CENTER_RIGHT,
    "swing": HorizontalVane.SWING,
}
VANE_TO_HORIZONTAL_OPTION: dict[HorizontalVane, str] = {
    v: k for k, v in HORIZONTAL_VANE_OPTIONS.items()
}
