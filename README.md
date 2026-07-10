# mudra-lsl

Stream raw surface-EMG (sEMG) from a **[Mudra Link](https://www.wearabledevices.co.il/)**
wristband (Wearable Devices Ltd.) to **[Lab Streaming Layer (LSL)](https://labstreaminglayer.org/)**.

`mudra-lsl` connects to the band over Bluetooth Low Energy, decodes its raw sEMG
stream with the published [`mudraka`](https://github.com/ttktjmt/mudraka) engine,
and republishes it as an LSL outlet — so any LSL-aware tool (LabRecorder, BCI
pipelines, MNE-Python, real-time visualisers) can consume it.

It is a thin, well-behaved **LSL bridge**, not a general-purpose Mudra SDK. The
one thing it does, it aims to do correctly.

> **Why this exists.** The Mudra Link's raw EMG is easy to *decode* (that is
> [`mudraka`](https://github.com/ttktjmt/mudraka)'s job) but there is no
> off-the-shelf way to get it onto LSL, the lingua franca of biosignal
> recording and BCI research. `mudra-lsl` fills exactly that gap.

## Status

**v1 — EMG only.** This release streams the 3-channel sEMG signal and nothing
else. IMU, gestures, pressure, navigation, and battery all exist on the device
but are intentionally out of scope for now — see the [roadmap](#roadmap).

## Features

- 🔌 Scan for and connect to a Mudra Link over BLE (`bleak`).
- 🧠 Decode raw sEMG via `mudraka` (the same engine used elsewhere in the Mudra
  tooling family).
- 📡 Publish a single 3-channel `float32` EMG outlet over LSL (`mne-lsl`), with
  proper channel labels, types, and units baked into the stream metadata.
- 🆔 Stable `source_id` derived from the device's hardware serial number, so
  recordings can be tied to a specific physical band across sessions and
  platforms.
- ♻️ Automatic reconnection with backoff, plus a `--forget` escape hatch for the
  macOS/CoreBluetooth "stale link" trap.
- 🧪 Offline, device-free tests that replay synthetic BLE frames through the real
  decode + publish path.

## Requirements

- **Python ≥ 3.11** (required by `mne-lsl`).
- A **Mudra Link** wristband, powered on and in BLE range.
- A working Bluetooth adapter. On Linux, `bleak` uses BlueZ; on macOS,
  CoreBluetooth; on Windows, WinRT.

## Installation

```bash
pip install mudra-lsl
```

Or, with [uv](https://docs.astral.sh/uv/):

```bash
uv add mudra-lsl
```

## Quick start

Scan for nearby bands:

```bash
mudra-lsl scan
```

Start streaming (scans, connects to the single match, publishes the outlet):

```bash
mudra-lsl stream -v
```

Connect to a specific device and skip scanning:

```bash
mudra-lsl stream --address <ADDRESS-OR-UUID> -v
```

Press `Ctrl-C` to stop; the SNC stream is disabled and the band disconnected
cleanly on exit.

### As a library

```python
import mudra_lsl

# Blocks until Ctrl-C (or `duration` seconds, if given).
mudra_lsl.stream()

# Connect directly, run for 10 seconds:
mudra_lsl.stream(address="XX:XX:XX:XX:XX:XX", duration=10.0)
```

For embedding in your own asyncio application:

```python
import asyncio
from mudra_lsl import MudraLslApp

async def main():
    app = MudraLslApp(stream_name="MudraEMG")
    await app.run()

asyncio.run(main())
```

## The LSL stream

| Property        | Value                                                        |
|-----------------|--------------------------------------------------------------|
| Stream name     | `MudraEMG` (configurable with `--stream-name`)               |
| Stream type     | `EMG`                                                        |
| Channels        | 3 — `ulnar`, `median`, `radial` (fixed order)                |
| Channel type    | `emg`                                                        |
| Channel unit    | `microvolts`                                                 |
| Sample format   | `float32`                                                    |
| Sampling rate   | 834 Hz (read from `mudraka`, not hardcoded)                  |
| `source_id`     | device hardware serial (see below)                           |

Extra metadata is attached to the stream's `desc()` for reproducibility:
`manufacturer`, `device_model`, `firmware_version`, and a `scale_note`.

> ### ⚠️ The amplitude scale is provisional
>
> Values are published in microvolts using `mudraka`'s scale of
> **0.035 µV/count**. This figure is **provisional and unverified** — it is
> *not* vendor-calibrated. Treat the signal as a **relative amplitude**, not an
> absolute physical measurement, until a proper calibration exists. This caveat
> is carried in the stream's `scale_note` metadata as well as here.

### Why `source_id` is the serial number, not the BLE address

LSL consumers use `source_id` to decide "is this the same physical device as
last time." The BLE address is a poor key for that: on macOS `bleak` surfaces a
CoreBluetooth-assigned UUID rather than the hardware MAC, and even on
Linux/Windows the address can change (privacy-mode randomisation, adapter
swaps). The device's own serial number is stable across platforms and
reconnects, so `mudra-lsl` reads it once at connect time (GATT `0x2a25` /
`0x2a27`) and uses it as the `source_id`. If the serial can't be read, it falls
back to the BLE address and logs a warning.

## Consuming the stream

Any LSL client works. For example, record to XDF with
[LabRecorder](https://github.com/labstreaminglayer/App-LabRecorder), or pull it
into Python:

```python
from mne_lsl.lsl import resolve_streams, StreamInlet

stream = resolve_streams(name="MudraEMG")[0]
inlet = StreamInlet(stream)
samples, timestamps = inlet.pull_chunk()
```

See [`examples/`](examples/) for runnable scripts, including exporting a short
recording to an MNE `Raw` object.

## How it works

```
Mudra Link ──BLE notify (0xfff4)──▶ mudra_lsl.app
                                       │  feed(frame, recv_time)
                                       ▼
                                 mudraka.Stream  (ring buffer, decode)
                                       │  pull_uv_into(cursor, buf)
                                       ▼
                                 EmgPublisher ──push_chunk──▶ LSL outlet
```

- `app.py` owns the BLE connection and one `mudraka.Stream`. Every 0xfff4
  notification is fed to the stream verbatim; on a timer, each publisher drains
  new samples and pushes them.
- `publishers/emg.py` owns its read cursor, the LSL outlet, and the
  channel-major → sample-major transpose that LSL requires.
- The `StreamPublisher` seam (`publishers/base.py`) is the extension point:
  adding IMU (Phase 2) or discrete-event Markers (Phase 3) is a new publisher
  class, not a rewrite.

Timestamps are left to LSL's `push_chunk` auto-timestamping (stamped at push
time and back-filled at the nominal rate), matching the `muse-lsl` /
`OpenBCI_LSL` convention. See [`docs/adr/`](docs/adr/) for the reasoning.

## Roadmap

`mudra-lsl` aims to eventually cover everything the Mudra Link can communicate.
The path there is deliberately incremental:

1. **Phase 1 (this release): EMG only.** A correct, well-tested single-stream
   bridge.
2. **Phase 2: IMU.** Once `mudraka` gains an IMU decoder, add a second
   publisher.
3. **Phase 3: discrete events.** Gesture / pressure / navigation / button as an
   LSL irregular-rate Markers stream; possibly battery/status as a low-rate
   auxiliary stream.

Capabilities we'd like from `mudraka` to enable later phases are tracked in
[`docs/mudraka-wishlist.md`](docs/mudraka-wishlist.md).

## Non-goals

- No IMU / gesture / pressure / navigation / battery streaming (yet — see
  roadmap).
- **One band per process.** Bilateral EMG means running two `mudra-lsl`
  processes, each with its own `source_id`-disambiguated outlet — matching
  `muse-lsl`'s model.
- Not a Mudra SDK. Decode is delegated to `mudraka`; this project only bridges
  to LSL.

## Development

```bash
uv sync                 # create the venv and install everything
uv run pytest           # run the offline test suite
uv run ruff check .     # lint
```

The default test suite needs no BLE hardware or LSL network: it replays
synthetic sEMG frames through the real `mudraka` decode path and asserts on what
gets pushed to a fake outlet. Tests that need a real band are marked `device`
and skipped by default (run with `uv run pytest -m device`).

## Acknowledgements

- [`mudraka`](https://github.com/ttktjmt/mudraka) — the sEMG decode engine this
  bridge is built on.
- [`mne-lsl`](https://github.com/mne-tools/mne-lsl) — the LSL binding used for
  the outlet.
- [`bleak`](https://github.com/hbldh/bleak) — cross-platform BLE.
- [`muse-lsl`](https://github.com/alexandrebarachant/muse-lsl) and
  [`OpenBCI_LSL`](https://github.com/openbci-archive/OpenBCI_LSL) — reference
  designs for wearable-to-LSL bridges.

<!-- TODO(human): confirm RawData license terms and third-party project
     positioning with Wearable Devices before any public release. -->

## License

Apache License 2.0 — see [LICENSE](LICENSE). This matches `mudraka`'s own
license, so there is no cross-license friction within the Mudra tooling family.
