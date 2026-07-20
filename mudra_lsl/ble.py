"""BLE transport for the Mudra Link (thin wrapper over :mod:`bleak`).

This module owns everything device-specific about talking to the band over
Bluetooth Low Energy: scanning, connecting, reading identity characteristics,
enabling/disabling the SNC (sEMG) stream, and subscribing to notifications.
The reconnection *policy*, including backoff timing (:func:`backoff_delay`),
lives in the orchestrator's ``_supervise`` loop (:mod:`mudra_lsl.app`), not here.

It deliberately knows nothing about ``mudraka`` or LSL — it just hands raw
notification bytes to a callback.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from . import constants

log = logging.getLogger("mudra_lsl.ble")

NotificationHandler = Callable[[int, bytearray], None]


@dataclass(frozen=True)
class DeviceInfo:
    """Identity read from the band at connect time."""

    address: str
    name: str | None
    serial: int | None
    #: Where ``serial`` came from: "device" (0x2a25/0x2a27) or "ble_address"
    #: (fallback when the serial characteristics could not be read/parsed).
    serial_source: str
    firmware: str | None

    @property
    def source_id(self) -> str:
        """The value to use as the LSL ``source_id``.

        Prefer the hardware serial; fall back to the BLE address so the outlet
        is still usable (with a warning logged at read time) if the serial
        characteristics are unavailable.
        """
        if self.serial is not None:
            return str(self.serial)
        return self.address


async def scan(
    *,
    name_substring: str = constants.DEVICE_NAME_SUBSTRING,
    timeout: float = 5.0,
    adapter: str | None = None,
) -> list[BLEDevice]:
    """Scan for advertising devices whose name contains ``name_substring``.

    Returns the matching :class:`BLEDevice` objects. The name is matched
    case-insensitively against both the device name and the advertised local
    name (either can be ``None`` depending on platform / advertisement).
    """
    kwargs = {"timeout": timeout, "return_adv": True}
    if adapter is not None:
        kwargs["bluez"] = {"adapter": adapter}
    discovered = await BleakScanner.discover(**kwargs)

    needle = name_substring.lower()
    matches: list[BLEDevice] = []
    for device, adv in discovered.values():
        names = [n for n in (device.name, getattr(adv, "local_name", None)) if n]
        if any(needle in n.lower() for n in names):
            matches.append(device)
    return matches


async def find_device(
    *,
    address: str | None = None,
    name_substring: str = constants.DEVICE_NAME_SUBSTRING,
    timeout: float = 5.0,
    adapter: str | None = None,
) -> BLEDevice | str:
    """Resolve a device to connect to.

    If ``address`` is given it is returned as-is (bleak connects by address
    string directly). Otherwise a scan is run and a single match is required;
    ambiguous or empty scans raise :class:`RuntimeError` with a helpful message.
    """
    if address is not None:
        return address

    matches = await scan(name_substring=name_substring, timeout=timeout, adapter=adapter)
    if not matches:
        raise RuntimeError(
            f"no BLE device advertising a name containing {name_substring!r} was found. "
            "Make sure the band is on and in range, or pass --address."
        )
    if len(matches) > 1:
        listing = ", ".join(f"{d.name or '?'} ({d.address})" for d in matches)
        raise RuntimeError(
            f"multiple Mudra devices found: {listing}. Disambiguate with --address."
        )
    return matches[0]


class MudraLinkConnection:
    """A single BLE session with one Mudra Link band.

    Intentionally low-level: the caller decides when to connect, read identity,
    enable SNC, subscribe, and tear down. The reconnection *policy* lives in
    the orchestrator's ``_supervise`` loop (:mod:`mudra_lsl.app`), not here.
    """

    def __init__(
        self,
        target: BLEDevice | str,
        *,
        adapter: str | None = None,
        connect_timeout: float = 30.0,
        on_disconnect: Callable[[], None] | None = None,
    ) -> None:
        self._target = target
        self._on_disconnect = on_disconnect
        client_kwargs: dict = {"timeout": connect_timeout}
        if adapter is not None:
            client_kwargs["bluez"] = {"adapter": adapter}
        self._client = BleakClient(
            target,
            disconnected_callback=self._handle_disconnect,
            **client_kwargs,
        )
        self._notifying = False

    # -- lifecycle ------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    @property
    def address(self) -> str:
        return self._client.address

    def _handle_disconnect(self, _client: BleakClient) -> None:
        log.info("BLE link to %s dropped", self.address)
        if self._on_disconnect is not None:
            self._on_disconnect()

    async def connect(self) -> None:
        await self._client.connect()
        log.info("connected to %s", self.address)

    async def disconnect(self) -> None:
        try:
            await self._client.disconnect()
        except Exception as exc:  # noqa: BLE001 - teardown must not raise
            log.debug("error during disconnect (ignored): %s", exc)

    # -- identity -------------------------------------------------------------

    async def _read_char_text(self, uuid: str) -> str | None:
        try:
            raw = await self._client.read_gatt_char(uuid)
        except Exception as exc:  # noqa: BLE001 - optional metadata, never fatal
            log.debug("could not read characteristic %s: %s", uuid, exc)
            return None
        return bytes(raw).decode("utf-8", errors="ignore").strip().strip("\x00").strip() or None

    async def read_device_info(self) -> DeviceInfo:
        """Read serial + firmware. Best-effort: never raises on read failure."""
        serial: int | None = None
        serial_source = "ble_address"
        try:
            left_raw = await self._client.read_gatt_char(constants.SERIAL_LEFT_CHAR_UUID)
            right_raw = await self._client.read_gatt_char(constants.SERIAL_RIGHT_CHAR_UUID)
            left = constants.parse_serial_field(bytes(left_raw))
            right = constants.parse_serial_field(bytes(right_raw))
            serial = constants.combine_serial(left, right)
            serial_source = "device"
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "could not read device serial (0x2a25/0x2a27): %s; "
                "falling back to BLE address for source_id",
                exc,
            )

        firmware = await self._read_char_text(constants.FIRMWARE_CHAR_UUID)

        info = DeviceInfo(
            address=self.address,
            name=getattr(self._target, "name", None),
            serial=serial,
            serial_source=serial_source,
            firmware=firmware,
        )
        log.info(
            "device info: serial=%s (%s) firmware=%s",
            info.serial,
            info.serial_source,
            info.firmware,
        )
        return info

    # -- SNC stream -----------------------------------------------------------

    async def enable_snc(self) -> None:
        await self._client.write_gatt_char(
            constants.COMMAND_CHAR_UUID, constants.CMD_ENABLE_SNC, response=True
        )
        log.info("SNC stream enabled")

    async def disable_snc(self) -> None:
        try:
            await self._client.write_gatt_char(
                constants.COMMAND_CHAR_UUID, constants.CMD_DISABLE_SNC, response=True
            )
            log.info("SNC stream disabled")
        except Exception as exc:  # noqa: BLE001 - clean-shutdown best effort
            log.debug("could not disable SNC (ignored during teardown): %s", exc)

    async def start_notify(self, handler: NotificationHandler) -> None:
        await self._client.start_notify(constants.SNC_CHAR_UUID, handler)
        self._notifying = True

    async def stop_notify(self) -> None:
        if not self._notifying:
            return
        try:
            await self._client.stop_notify(constants.SNC_CHAR_UUID)
        except Exception as exc:  # noqa: BLE001
            log.debug("could not stop notifications (ignored): %s", exc)
        finally:
            self._notifying = False


def backoff_delay(attempt: int, *, base: float = 1.0, cap: float = 30.0) -> float:
    """Exponential backoff (1, 2, 4, ... capped) for reconnect attempts."""
    return min(cap, base * (2**attempt))
