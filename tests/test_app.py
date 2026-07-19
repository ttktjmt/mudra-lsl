"""App-orchestrator tests with a fake BLE connection (no radio, no LSL net).

These exercise the parts unit tests can't: the notification -> feed wiring, the
poll loop, duration-based stop, clean teardown, and reconnection (the publisher
and its outlet must persist across a dropped link).
"""

from __future__ import annotations

import asyncio

import numpy as np
from conftest import RecordingFactory
from fixtures import synth

import mudra_lsl.app as app_module
from mudra_lsl.ble import DeviceInfo

DEVICE_INFO = DeviceInfo(
    address="FA:KE:00:00:00:01",
    name="Mudra Link",
    serial=7_000_042,
    serial_source="device",
    firmware="1.2.3",
)


class FakeConnection:
    """Feeds a preset session's frames through the notify handler on connect."""

    session: synth.Session | None = None
    instances: list[FakeConnection] = []

    def __init__(self, target, *, adapter=None, connect_timeout=30.0, on_disconnect=None):
        self.target = target
        self.on_disconnect = on_disconnect
        self.enabled = False
        self.disabled = False
        self.notifying = False
        self.disconnected = False
        self.handler = None
        FakeConnection.instances.append(self)

    @property
    def is_connected(self):
        return not self.disconnected

    @property
    def address(self):
        return DEVICE_INFO.address

    async def connect(self):
        pass

    async def read_device_info(self):
        return DEVICE_INFO

    async def enable_snc(self):
        self.enabled = True

    async def start_notify(self, handler):
        self.handler = handler
        self.notifying = True
        for frame in self.session.frames:
            handler(0, bytearray(frame))

    async def stop_notify(self):
        self.notifying = False

    async def disable_snc(self):
        self.disabled = True

    async def disconnect(self):
        self.disconnected = True


def test_app_streams_session_to_outlet_and_tears_down_cleanly(monkeypatch):
    session = synth.build_session(n_frames=15)
    FakeConnection.session = session
    FakeConnection.instances = []
    factory = RecordingFactory()

    async def fake_find_device(**kwargs):
        return DEVICE_INFO.address

    monkeypatch.setattr(app_module.ble, "find_device", fake_find_device)
    monkeypatch.setattr(app_module.ble, "MudraLinkConnection", FakeConnection)

    application = app_module.MudraLslApp(
        address=DEVICE_INFO.address,
        duration=0.15,
        poll_interval=0.02,
        outlet_factory=factory,
    )
    asyncio.run(application.run())

    out = factory.outlet.all_samples
    assert out.shape == (session.n_samples, 3)
    np.testing.assert_allclose(out, session.expected_uv(), rtol=1e-4, atol=1e-3)

    # source_id came from the device serial, and the LSL info reflects it.
    assert factory.outlet.sinfo.source_id == "7000042"

    conn = FakeConnection.instances[0]
    assert conn.enabled is True
    assert conn.disabled is True  # clean shutdown disables SNC
    assert conn.disconnected is True
    assert conn.notifying is False


class ReconnectingConnection(FakeConnection):
    """First instance drops mid-stream; later instances stream cleanly."""

    sessions: list[synth.Session] = []

    def __init__(self, target, *, adapter=None, connect_timeout=30.0, on_disconnect=None):
        super().__init__(target, adapter=adapter, connect_timeout=connect_timeout,
                         on_disconnect=on_disconnect)
        self.idx = len(FakeConnection.instances) - 1

    async def start_notify(self, handler):
        self.handler = handler
        self.notifying = True
        for frame in self.sessions[self.idx].frames:
            handler(0, bytearray(frame))
        if self.idx == 0 and self.on_disconnect is not None:
            self.on_disconnect()  # simulate an unexpected drop after the first batch


class AlwaysDropsConnection(FakeConnection):
    """Every connection streams one frame then drops the link immediately.

    Simulates a device that connects fine but never stays up (e.g. a
    persistent RF/firmware issue) — the scenario ``--max-reconnect-attempts``
    is meant to bound even though each individual ``connect()`` succeeds.
    """

    session: synth.Session | None = None

    async def start_notify(self, handler):
        self.handler = handler
        self.notifying = True
        for frame in self.session.frames:
            handler(0, bytearray(frame))
        if self.on_disconnect is not None:
            self.on_disconnect()


def test_max_reconnect_attempts_bounds_repeated_link_drops(monkeypatch):
    """A link that drops every time it (re)connects must not retry forever.

    Regression test: the reconnect path used to reset its attempt counter to
    zero on every successful ``connect()``, so a device that connected fine
    but dropped immediately after streaming evaded ``--max-reconnect-attempts``
    entirely and retried without limit. Only outright connect *exceptions*
    were ever bounded.
    """
    session = synth.build_session(n_frames=4)
    AlwaysDropsConnection.session = session
    FakeConnection.instances = []

    async def fake_find_device(**kwargs):
        return DEVICE_INFO.address

    monkeypatch.setattr(app_module.ble, "find_device", fake_find_device)
    monkeypatch.setattr(app_module.ble, "MudraLinkConnection", AlwaysDropsConnection)
    monkeypatch.setattr(app_module.ble, "backoff_delay", lambda *a, **k: 0.0)

    application = app_module.MudraLslApp(
        address=DEVICE_INFO.address,
        max_reconnect_attempts=2,
        poll_interval=0.01,
        outlet_factory=RecordingFactory(),
    )
    # No `duration` set: without the cap this would hang forever redialing a
    # link that always drops. A bounded run proves the cap was honored.
    asyncio.run(asyncio.wait_for(application.run(), timeout=5.0))

    # The initial connection plus exactly 2 reconnect attempts, then give up
    # (if the cap were not honored, wait_for above would time out instead).
    assert len(FakeConnection.instances) == 3


def test_app_reconnects_and_outlet_persists_across_drop(monkeypatch):
    s0 = synth.build_session(n_frames=8, seed=1)
    s1 = synth.build_session(n_frames=8, seed=2)
    FakeConnection.instances = []
    ReconnectingConnection.sessions = [s0, s1]
    factory = RecordingFactory()

    async def fake_find_device(**kwargs):
        return DEVICE_INFO.address

    monkeypatch.setattr(app_module.ble, "find_device", fake_find_device)
    monkeypatch.setattr(app_module.ble, "MudraLinkConnection", ReconnectingConnection)
    monkeypatch.setattr(app_module.ble, "backoff_delay", lambda *a, **k: 0.01)

    application = app_module.MudraLslApp(
        address=DEVICE_INFO.address,
        duration=0.3,
        poll_interval=0.02,
        outlet_factory=factory,
    )
    asyncio.run(application.run())

    # Reconnected at least once; the persistent outlet accumulated both batches.
    assert len(FakeConnection.instances) >= 2
    out = factory.outlet.all_samples
    expected = np.concatenate([s0.expected_uv(), s1.expected_uv()], axis=0)
    assert out.shape == (s0.n_samples + s1.n_samples, 3)
    np.testing.assert_allclose(out, expected, rtol=1e-4, atol=1e-3)

    # The dropped connection was not cleanly disabled; the final one was.
    assert FakeConnection.instances[0].disabled is False
    assert FakeConnection.instances[-1].disabled is True
