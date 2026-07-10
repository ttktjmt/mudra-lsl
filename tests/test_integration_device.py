"""Manual integration test — requires a real Mudra Link band.

Skipped by default. To run it, power on a band in BLE range and set the
environment variable::

    MUDRA_LSL_DEVICE_TEST=1 uv run pytest -m device -s

It exercises the full real pipeline: scan -> connect -> read serial/firmware ->
enable SNC -> collect notifications -> confirm decoded samples flow.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest

pytestmark = [
    pytest.mark.device,
    pytest.mark.skipif(
        os.environ.get("MUDRA_LSL_DEVICE_TEST") != "1",
        reason="requires a real Mudra Link; set MUDRA_LSL_DEVICE_TEST=1 to run",
    ),
]


def test_live_emg_flows():
    import mudraka

    from mudra_lsl import ble

    async def run() -> tuple[int, object]:
        target = await ble.find_device(timeout=10.0)
        conn = ble.MudraLinkConnection(target)
        await conn.connect()
        try:
            info = await conn.read_device_info()
            cfg = mudraka.Config()
            stream = mudraka.Stream(cfg)
            await conn.enable_snc()
            await conn.start_notify(lambda _s, data: stream.feed(bytes(data), time.monotonic()))
            await asyncio.sleep(2.0)
            await conn.stop_notify()
            await conn.disable_snc()
            return stream.stats().total_written, info
        finally:
            await conn.disconnect()

    total_written, info = asyncio.run(run())
    print(f"device serial={info.serial} firmware={info.firmware} samples={total_written}")
    assert total_written > 0, "no sEMG samples decoded from the live device"
