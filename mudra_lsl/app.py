"""Orchestrator: wire BLE notifications into mudraka and drive LSL publishers.

Owns exactly one ``mudraka.Stream`` and one BLE connection for the process
lifetime. On each 0xfff4 notification it feeds the frame to the stream; on a
timer it ticks every active publisher. In v1 there is a single publisher
(EMG), but the loop shape already supports more (Phase 2/3).

Reconnection: the LSL outlet is created once and kept up across BLE drops, so
consumers stay connected through a reconnect — there is just a logged gap in the
samples for the duration of the outage (matching muse-lsl's behaviour).
"""

from __future__ import annotations

import asyncio
import logging
import time

import mudraka

from . import ble, constants
from .publishers import EmgPublisher, StreamPublisher

log = logging.getLogger("mudra_lsl.app")


class MudraLslApp:
    """Connect to a Mudra Link band and publish its EMG stream over LSL."""

    def __init__(
        self,
        *,
        address: str | None = None,
        name_substring: str = constants.DEVICE_NAME_SUBSTRING,
        adapter: str | None = None,
        poll_interval: float = 0.02,
        reconnect: bool = True,
        max_reconnect_attempts: int | None = None,
        forget: bool = False,
        stream_name: str = "MudraEMG",
        scan_timeout: float = 5.0,
        connect_timeout: float = 30.0,
        duration: float | None = None,
        outlet_factory=None,
    ) -> None:
        self._address = address
        self._name_substring = name_substring
        self._adapter = adapter
        self._poll_interval = poll_interval
        self._reconnect = reconnect
        self._max_reconnect_attempts = max_reconnect_attempts
        self._forget = forget
        self._stream_name = stream_name
        self._scan_timeout = scan_timeout
        self._connect_timeout = connect_timeout
        self._duration = duration
        self._outlet_factory = outlet_factory

        self._config: mudraka.Config | None = None
        self._stream: mudraka.Stream | None = None
        self._publishers: list[StreamPublisher] = []
        self._conn: ble.MudraLinkConnection | None = None

        self._running = False
        self._link_lost = False
        self._reconnect_attempt = 0
        self._wake: asyncio.Event | None = None

    # -- public API -----------------------------------------------------------

    async def run(self) -> None:
        """Run until stopped (Ctrl-C / :meth:`stop`) or ``duration`` elapses."""
        self._running = True
        self._link_lost = False
        self._wake = asyncio.Event()
        self._config = mudraka.Config()
        self._stream = mudraka.Stream(self._config)

        duration_task: asyncio.Task | None = None
        if self._duration is not None:
            duration_task = asyncio.ensure_future(self._duration_timer())

        try:
            await self._supervise()
        finally:
            if duration_task is not None:
                duration_task.cancel()
            await self._shutdown()

    def stop(self) -> None:
        """Request a clean shutdown (safe to call from anywhere on the loop)."""
        self._running = False
        if self._wake is not None:
            self._wake.set()

    # -- supervision loop -----------------------------------------------------

    async def _supervise(self) -> None:
        while self._running:
            conn: ble.MudraLinkConnection | None = None
            try:
                target = await self._resolve_target()
                conn = ble.MudraLinkConnection(
                    target,
                    adapter=self._adapter,
                    connect_timeout=self._connect_timeout,
                    on_disconnect=self._on_link_lost,
                )
                self._conn = conn
                self._link_lost = False
                await conn.connect()

                if not self._publishers:
                    info = await conn.read_device_info()
                    self._build_publishers(info)

                await conn.enable_snc()
                await conn.start_notify(self._on_notification)
                log.info("streaming EMG over LSL; press Ctrl-C to stop")

                await self._poll_loop()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - connect/setup failures
                if not self._running:
                    break
                if not self._reconnect:
                    log.error("connection failed and --no-reconnect set: %s", exc)
                    break
                if not await self._handle_reconnect(f"connection error: {exc}"):
                    break
                continue
            finally:
                if conn is not None:
                    await self._teardown_conn(conn, clean=not self._running)

            # _poll_loop returned without raising: either a clean stop or a
            # link drop detected mid-stream.
            if not self._running:
                break
            if self._link_lost:
                if not self._reconnect:
                    log.warning("link lost and --no-reconnect set; stopping")
                    break
                if not await self._handle_reconnect("link lost"):
                    break

    async def _handle_reconnect(self, reason: str) -> bool:
        """Count a reconnect attempt, back off, and check the attempt cap.

        Shared by both failure modes that require a fresh connection: an
        outright connect/setup exception, and a link dropped mid-stream after
        a prior connect succeeded. Both count against ``--max-reconnect-
        attempts`` — a device that connects fine but drops repeatedly right
        after is just as much a "failed reconnect" as one that never connects,
        so the cap must not reset on every transient success. Returns True to
        keep retrying.
        """
        self._reconnect_attempt += 1
        if (
            self._max_reconnect_attempts is not None
            and self._reconnect_attempt > self._max_reconnect_attempts
        ):
            log.error(
                "giving up after %d reconnect attempts (%s)", self._reconnect_attempt - 1, reason
            )
            return False
        delay = ble.backoff_delay(self._reconnect_attempt - 1)
        log.warning(
            "%s; retrying in %.1fs (attempt %d)",
            reason,
            delay,
            self._reconnect_attempt,
        )
        await self._sleep_or_wake(delay)
        return True

    async def _poll_loop(self) -> None:
        assert self._wake is not None
        while self._running and not self._link_lost:
            self._wake.clear()
            for pub in self._publishers:
                self._safe_poll(pub)
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self._poll_interval)
            except TimeoutError:
                pass  # normal tick
        # Final drain so samples buffered right up to the stop/drop get pushed.
        for pub in self._publishers:
            self._safe_poll(pub)

    def _safe_poll(self, pub: StreamPublisher) -> None:
        try:
            pub.poll_and_push()
        except Exception as exc:  # noqa: BLE001 - one publisher must not kill the loop
            log.error("publisher %s failed to push: %s", type(pub).__name__, exc)

    # -- wiring ---------------------------------------------------------------

    def _on_notification(self, _sender: int, data: bytearray) -> None:
        # Called by bleak on the event loop for every 0xfff4 notification.
        assert self._stream is not None
        try:
            self._stream.feed(bytes(data), time.monotonic())
        except Exception as exc:  # noqa: BLE001 - a bad frame must not kill the link
            log.warning("failed to feed %d-byte frame: %s", len(data), exc)

    def _on_link_lost(self) -> None:
        self._link_lost = True
        if self._wake is not None:
            self._wake.set()

    def _build_publishers(self, info: ble.DeviceInfo) -> None:
        assert self._stream is not None and self._config is not None
        if info.serial_source != "device":
            log.warning(
                "using BLE address as LSL source_id (%s); the hardware serial "
                "would be more stable across reconnects",
                info.source_id,
            )
        emg_kwargs = dict(
            source_id=info.source_id,
            firmware=info.firmware,
            name=self._stream_name,
        )
        if self._outlet_factory is not None:
            emg_kwargs["outlet_factory"] = self._outlet_factory
        emg = EmgPublisher(self._stream, self._config.profile, **emg_kwargs)
        self._publishers = [emg]

    # -- device resolution ----------------------------------------------------

    async def _resolve_target(self):
        if self._forget:
            # Fresh scan every attempt to obtain a new BLEDevice handle rather
            # than reusing a possibly-retained one (the macOS/CoreBluetooth
            # reconnect trap). Match by address if given, else by name.
            matches = await ble.scan(
                name_substring=self._name_substring,
                timeout=self._scan_timeout,
                adapter=self._adapter,
            )
            if self._address is not None:
                for device in matches:
                    if device.address.lower() == self._address.lower():
                        return device
                raise RuntimeError(f"--forget rescan did not find address {self._address}")
            if not matches:
                raise RuntimeError("no Mudra device found on rescan")
            if len(matches) > 1:
                raise RuntimeError("multiple Mudra devices found; disambiguate with --address")
            return matches[0]

        return await ble.find_device(
            address=self._address,
            name_substring=self._name_substring,
            timeout=self._scan_timeout,
            adapter=self._adapter,
        )

    # -- teardown -------------------------------------------------------------

    async def _sleep_or_wake(self, delay: float) -> None:
        assert self._wake is not None
        self._wake.clear()
        try:
            await asyncio.wait_for(self._wake.wait(), timeout=delay)
        except TimeoutError:
            pass

    async def _teardown_conn(self, conn: ble.MudraLinkConnection, *, clean: bool) -> None:
        await conn.stop_notify()
        if clean:
            await conn.disable_snc()
        await conn.disconnect()
        if self._conn is conn:
            self._conn = None

    async def _duration_timer(self) -> None:
        try:
            await asyncio.sleep(self._duration)  # type: ignore[arg-type]
        except asyncio.CancelledError:
            return
        log.info("requested duration (%.1fs) elapsed; stopping", self._duration)
        self.stop()

    async def _shutdown(self) -> None:
        for pub in self._publishers:
            try:
                pub.close()
            except Exception as exc:  # noqa: BLE001
                log.debug("error closing publisher (ignored): %s", exc)
        self._publishers = []
        if self._conn is not None:
            await self._teardown_conn(self._conn, clean=True)
        log.info("shutdown complete")
