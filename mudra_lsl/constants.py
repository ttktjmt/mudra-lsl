"""Static BLE facts for the Mudra Link wristband.

Sourced from Wearable Devices' ``MUDRA_LINK_SIGNAL_SPEC.md``. Only the subset
needed for the v1 EMG-only bridge lives here; IMU / gesture / battery
characteristics exist on the device but are intentionally out of scope (see the
README roadmap).
"""

from __future__ import annotations


def uuid16(short: int) -> str:
    """Expand a 16-bit GATT UUID into its full 128-bit string form.

    Bluetooth SIG assigns 16-bit UUIDs that live inside the standard base UUID
    ``0000xxxx-0000-1000-8000-00805f9b34fb``. bleak accepts the full form on
    every backend, so we normalise here rather than passing bare integers.
    """
    return f"0000{short:04x}-0000-1000-8000-00805f9b34fb"


# --- Device discovery ---------------------------------------------------------

# The advertised BLE name contains "mudra" (case-insensitive); used to filter
# scan results.
DEVICE_NAME_SUBSTRING = "mudra"


# --- GATT characteristics -----------------------------------------------------

# sEMG ("SNC") stream, delivered via notifications.
SNC_CHAR_UUID = uuid16(0xFFF4)

# Control channel; enable/disable commands are *written* here.
COMMAND_CHAR_UUID = uuid16(0xFFF1)

# Standard GATT serial-number strings, one per band. Read-only hex strings.
SERIAL_RIGHT_CHAR_UUID = uuid16(0x2A25)
SERIAL_LEFT_CHAR_UUID = uuid16(0x2A27)

# Standard GATT firmware-revision string (UTF-8, e.g. "1.2.3"). Read-only.
FIRMWARE_CHAR_UUID = uuid16(0x2A26)


# --- COMMAND payloads (written to COMMAND_CHAR_UUID) --------------------------

# Every stream is off by default; SNC must be enabled explicitly before any
# 0xfff4 notification arrives.
CMD_ENABLE_SNC = bytes((0x06, 0x00, 0x01))
CMD_DISABLE_SNC = bytes((0x06, 0x00, 0x00))


def combine_serial(left: int, right: int) -> int:
    """Combine the two per-band serial numbers into the device serial.

    Formula confirmed by the signal spec: ``left * 1_000_000 + right``. This is
    stable across platforms and reconnects, unlike the BLE address bleak
    surfaces (a CoreBluetooth UUID on macOS; a possibly-randomised MAC
    elsewhere), so it is what the LSL ``source_id`` is built from.
    """
    return left * 1_000_000 + right


def parse_serial_field(raw: bytes) -> int:
    """Parse a 0x2a25 / 0x2a27 serial-number characteristic value.

    The spec describes these as hex strings (e.g. ``b"1A2B"``). We decode as
    ASCII and parse base-16. Empty / unreadable values raise ``ValueError`` so
    the caller can fall back gracefully.
    """
    text = raw.decode("ascii", errors="ignore").strip().strip("\x00").strip()
    if not text:
        raise ValueError("empty serial characteristic value")
    return int(text, 16)
