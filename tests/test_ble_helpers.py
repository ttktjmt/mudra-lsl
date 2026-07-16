"""Unit tests for pure BLE helpers (no radio required)."""

from __future__ import annotations

import pytest

from mudra_lsl import constants
from mudra_lsl.ble import DeviceInfo, MudraLinkConnection, backoff_delay


def test_uuid16_expands_to_full_base_uuid():
    assert constants.uuid16(0xFFF4) == "0000fff4-0000-1000-8000-00805f9b34fb"
    assert constants.uuid16(0xFFF1) == "0000fff1-0000-1000-8000-00805f9b34fb"
    assert constants.uuid16(0x2A25) == "00002a25-0000-1000-8000-00805f9b34fb"


def test_known_characteristic_uuids():
    assert constants.SNC_CHAR_UUID == constants.uuid16(0xFFF4)
    assert constants.COMMAND_CHAR_UUID == constants.uuid16(0xFFF1)
    assert constants.SERIAL_RIGHT_CHAR_UUID == constants.uuid16(0x2A25)
    assert constants.SERIAL_LEFT_CHAR_UUID == constants.uuid16(0x2A27)
    assert constants.FIRMWARE_CHAR_UUID == constants.uuid16(0x2A26)


def test_command_payloads():
    assert constants.CMD_ENABLE_SNC == bytes([0x06, 0x00, 0x01])
    assert constants.CMD_DISABLE_SNC == bytes([0x06, 0x00, 0x00])


def test_combine_serial_formula():
    assert constants.combine_serial(3, 7) == 3_000_007
    assert constants.combine_serial(12, 345_678) == 12_345_678
    assert constants.combine_serial(0, 0) == 0


@pytest.mark.parametrize(
    "raw,expected",
    [
        (b"1A2B", 0x1A2B),
        (b"00FF", 0xFF),
        (b" 10 ", 0x10),
        (b"1a2b\x00", 0x1A2B),
        (b"\x000042\x00", 0x42),
    ],
)
def test_parse_serial_field(raw, expected):
    assert constants.parse_serial_field(raw) == expected


def test_parse_serial_field_rejects_empty():
    with pytest.raises(ValueError):
        constants.parse_serial_field(b"")
    with pytest.raises(ValueError):
        constants.parse_serial_field(b"\x00\x00")


def test_device_info_source_id_prefers_serial():
    info = DeviceInfo(
        address="AA:BB:CC", name="Mudra", serial=7_000_042, serial_source="device", firmware="1.0"
    )
    assert info.source_id == "7000042"


def test_device_info_source_id_falls_back_to_address():
    info = DeviceInfo(
        address="AA:BB:CC", name=None, serial=None, serial_source="ble_address", firmware=None
    )
    assert info.source_id == "AA:BB:CC"


def test_mudra_link_connection_accepts_adapter_kwarg():
    """Constructing with ``adapter=`` must keep working against the real bleak.

    bleak deprecated the flat ``adapter`` kwarg (in favour of
    ``bluez={"adapter": ...}``) starting in 3.0; every other test fakes
    ``MudraLinkConnection`` entirely, so nothing else exercises the real
    construction path. If a future bleak release drops the deprecated kwarg,
    this fails loudly instead of ``--adapter`` silently breaking in the field.
    """
    conn = MudraLinkConnection("AA:BB:CC:DD:EE:FF", adapter="hci0")
    assert conn.address == "AA:BB:CC:DD:EE:FF"


def test_backoff_delay_grows_then_caps():
    assert backoff_delay(0) == 1.0
    assert backoff_delay(1) == 2.0
    assert backoff_delay(2) == 4.0
    assert backoff_delay(3) == 8.0
    assert backoff_delay(20) == 30.0  # capped
    assert backoff_delay(0, base=0.5) == 0.5
