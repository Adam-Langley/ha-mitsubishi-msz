# Mitsubishi MSZ Local

Home Assistant integration that talks **directly** to a Mitsubishi Electric
indoor unit over your own network — no Mitsubishi cloud account, no MELView,
no internet connection required.

Developed and tested against an **MSZ-GL60VGD** with a **MAC-559IF-E** Wi-Fi
adapter.

## How it works

The MAC-559IF-E is normally a cloud bridge, but it also serves two
unauthenticated endpoints on port 80 of your LAN:

| Endpoint | Purpose |
| --- | --- |
| `POST /smart` | Returns the indoor unit's raw **CN105** frames as hex, and passes command frames back to the unit |
| `GET /unitinfo` | Adapter model, serial, firmware and signal strength |

CN105 is the native serial protocol on the indoor unit's control board — the
same one the adapter itself speaks over the ribbon cable. This integration
encodes and decodes those frames itself, so control is genuinely local and
takes effect immediately.

```
Home Assistant  ──HTTP──>  MAC-559IF-E  ──CN105 serial──>  MSZ-GL60VGD
        (your LAN only — the Mitsubishi cloud is never contacted)
```

> **Note:** ECHONET Lite, which most Mitsubishi Home Assistant integrations
> rely on, is **not** supported by the MAC-559IF-E — that is a MAC-568IF-E and
> later feature. This integration deliberately does not use it.

## What you get

A single device with these entities:

| Entity | Type | Notes |
| --- | --- | --- |
| Heat pump | `climate` | Off / Heat / Cool / Auto / Dry / Fan, setpoint 16–31 °C in 0.5 °C steps, 6 fan speeds, 7 vane positions |
| Horizontal vane | `select` | Ignored by models with manual louvres |
| Power saving | `switch` | Economy mode |
| Room temperature | `sensor` | The unit's own sensor, 0.5 °C resolution |
| Room temperature (secondary) | `sensor` | Second internal sensor, disabled by default |
| Outdoor temperature | `sensor` | Only created if your unit actually reports one |
| Power / Energy | `sensor` | Only meaningful on models with a power meter; the GL series reports zero |
| Compressor | `binary_sensor` | Whether the unit is actively running |
| Problem | `binary_sensor` | Fault flag, with the raw error code as a diagnostic sensor |
| Runtime, Wi-Fi signal, Error code | `sensor` | Diagnostic, disabled by default |

## Installation

### HACS (recommended)

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/Adam-Langley/ha-mitsubishi-msz`, type **Integration**
3. Install **Mitsubishi MSZ Local**, then restart Home Assistant
4. **Settings → Devices & Services → Add Integration → Mitsubishi MSZ Local**

The adapter is usually discovered automatically via DHCP (it announces a
`gainspan_*` hostname). Otherwise enter its IP address.

### Manual

Copy `custom_components/mitsubishi_msz` into your `config/custom_components/`
directory and restart Home Assistant.

## Configuration

Give the adapter a **static DHCP lease** on your router — the integration
identifies the device by MAC address, but it has to reach it by IP.

The poll interval defaults to 30 seconds and can be changed in the
integration's options. The adapter only refreshes its own snapshot of the
indoor unit about every 5 seconds, so polling faster gains nothing. For the
same reason a command is echoed back optimistically and confirmed by a
follow-up poll a few seconds later.

## Protocol notes

Frames are 22 bytes:

```
0       0xFC start byte
1       type: 0x62 / 0x7B response, 0x41 command
2..4    0x01 0x30 0x10 fixed header
5       segment (0x02 settings, 0x03 sensors, 0x04 errors, 0x06 energy)
6..20   payload
21      checksum: (0x100 - sum(bytes[1:21]) % 0x100) % 0x100
```

Commands always carry the unit's **complete** current state, with a control
bitmask naming the fields to act on, so changing one setting cannot disturb
another. Response and command frames use *different* offsets for the same
field — the half-degree setpoint is at byte 16 in a response and byte 19 in a
command.

## Credits

Frame field semantics were cross-checked against the
[pymitsubishi](https://github.com/pymitsubishi/pymitsubishi) project and
SwiCago's original [HeatPump](https://github.com/SwiCago/HeatPump)
reverse-engineering work. This integration shares no code with either and has
no third-party Python dependencies.

## License

MIT
