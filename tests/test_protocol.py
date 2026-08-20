"""Protocol tests built from frames captured off a real MSZ-GL60VGD.

These run without Home Assistant installed:  python3 -m pytest tests/
"""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "mitsubishi_msz"))

import protocol as p  # noqa: E402

# Captured from a MAC-559IF-E at rest: off, heat mode, 25.0 C, room 19.0 C.
LIVE_FRAMES = [
    "fc620130100200000001060107000003b20000000097",
    "fc62013010030000090001a6aafe0000000000000002",
    "fc6201301004000000800000000000000000000000d9",
    "fc620130100500000000000000000000000000000058",
    "fc620130100600000000000000000000000000000057",
    "fc620130100900000000000000000000000000000054",
]
PROFILE_FRAMES = [
    "fc7b013010c9030020001407758c25a0be94bea0be09",
    "fc7b013010cda0bea0bea0be0000000000000000005d",
]


@pytest.fixture
def general():
    return p.GeneralState.parse(p.parse_frames(LIVE_FRAMES)[p.SEG_GENERAL])


def test_every_captured_frame_validates():
    for hex_frame in LIVE_FRAMES + PROFILE_FRAMES:
        p.validate(bytes.fromhex(hex_frame))


def test_all_segments_are_indexed():
    segments = p.parse_frames(LIVE_FRAMES)
    assert set(segments) == {0x02, 0x03, 0x04, 0x05, 0x06, 0x09}


def test_general_state_decodes(general):
    assert general.power is False
    assert general.drive_mode is p.DriveMode.HEAT
    assert general.target_temp == 25.0
    assert general.fan_speed is p.FanSpeed.S1
    assert general.vertical_vane is p.VerticalVane.SWING
    assert general.horizontal_vane is p.HorizontalVane.CENTER
    assert general.power_saving is False


def test_sensor_state_decodes():
    sensor = p.SensorState.parse(p.parse_frames(LIVE_FRAMES)[p.SEG_SENSOR])
    assert sensor.room_temp == 19.0
    assert sensor.room_temp_secondary == 21.0
    # This model reports raw 0x01 here, which is not a real reading.
    assert sensor.outdoor_temp is None


def test_energy_and_error_states():
    segments = p.parse_frames(LIVE_FRAMES)
    energy = p.EnergyState.parse(segments[p.SEG_ENERGY])
    assert energy.operating is False
    error = p.ErrorState.parse(segments[p.SEG_ERROR])
    assert error.error_code == p.NO_ERROR
    assert error.has_error is False


@pytest.mark.parametrize(
    ("temperature", "expected"),
    [
        (24.0, "fc410130100104020001070107000000000003b04173"),
        (25.0, "fc410130100104020001060107000000000003b24172"),
    ],
)
def test_temperature_command_matches_accepted_frames(general, temperature, expected):
    """These exact bytes were accepted by the unit during testing."""
    state = copy.deepcopy(general)
    state.target_temp = temperature
    assert state.build_command(p.Controls.TEMPERATURE).hex() == expected


def test_half_degree_setpoint_round_trips(general):
    state = copy.deepcopy(general)
    state.target_temp = 22.5
    frame = state.build_command(p.Controls.TEMPERATURE)
    p.validate(frame)
    # Command frames carry the half-degree setpoint at index 19; response
    # frames put it at 16, so the two layouts must not be confused.
    assert (frame[19] - 0x80) / 2 == 22.5
    assert frame[10] == 31 - 22  # whole-degree field for older boards


def test_commands_always_set_outside_control(general):
    frame = general.build_command(p.Controls.POWER)
    controls = (frame[6] << 8) | frame[7]
    assert controls & p.Controls.OUTSIDE_CONTROL
    assert controls & p.Controls.POWER


def test_every_generated_command_is_self_consistent(general):
    for controls in (
        p.Controls.POWER,
        p.Controls.DRIVE_MODE,
        p.Controls.TEMPERATURE,
        p.Controls.FAN_SPEED,
        p.Controls.VERTICAL_VANE,
        p.Controls.HORIZONTAL_VANE,
    ):
        p.validate(general.build_command(controls))
    p.validate(general.build_extend_command(p.Controls08.POWER_SAVING))


def test_bad_checksum_is_rejected():
    broken = bytearray(bytes.fromhex(LIVE_FRAMES[0]))
    broken[-1] ^= 0xFF
    with pytest.raises(p.ProtocolError):
        p.validate(bytes(broken))


def test_short_frame_is_rejected():
    with pytest.raises(p.ProtocolError):
        p.validate(b"\xfc\x62\x01")


def test_garbage_frames_are_skipped_not_fatal():
    assert p.parse_frames(["not hex", "fc0000", ""]) == {}
