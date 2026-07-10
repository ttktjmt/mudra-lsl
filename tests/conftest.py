"""Shared test doubles and fixtures.

Everything here is offline: no BLE hardware, no LSL network. The ``FakeOutlet``
stands in for ``mne_lsl.lsl.StreamOutlet`` and the ``FakeStream`` stands in for
``mudraka.Stream`` so publisher logic can be tested in isolation. Tests that
want the *real* decode path use a real ``mudraka.Stream`` and only fake the
outlet.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest

# Make ``tests/fixtures`` importable as ``fixtures`` regardless of cwd.
sys.path.insert(0, str(Path(__file__).parent))


class FakeOutlet:
    """Records every chunk pushed to it.

    Crucially copies each chunk, because the real publisher reuses its push
    buffer between calls — a fake that stored the array by reference would see
    every recorded chunk mutate. (This also mirrors what liblsl does: copy in.)
    """

    def __init__(self, sinfo) -> None:
        self.sinfo = sinfo
        self.chunks: list[np.ndarray] = []
        self.timestamps: list = []
        self.closed = False

    def push_chunk(self, x, timestamp=None, pushThrough=True) -> None:  # noqa: N803
        self.chunks.append(np.array(x, copy=True))
        self.timestamps.append(timestamp)

    def close(self) -> None:
        self.closed = True

    @property
    def all_samples(self) -> np.ndarray:
        """All pushed samples concatenated, sample-major ``(n_total, n_ch)``."""
        if not self.chunks:
            return np.empty((0, self.sinfo.n_channels), dtype=np.float32)
        return np.concatenate(self.chunks, axis=0)


@dataclass
class FakeProfile:
    """Stand-in for ``mudraka`` ``StreamProfile``."""

    channels: int = 3
    channel_names: list[str] = field(
        default_factory=lambda: ["ulnar", "median", "radial"]
    )
    nominal_rate_hz: float = 834.0
    sample_width_bits: int = 16
    scale: list[float] = field(default_factory=lambda: [0.035, 0.035, 0.035])
    unit: str = "uV"


class FakeStream:
    """Faithful stand-in for the subset of ``mudraka.Stream`` we use.

    Holds a fixed pool of already-decoded µV samples (channel-major) and serves
    them through the same ``pull_uv_into`` contract: fill up to the buffer
    width, advance an absolute cursor, and report samples lost to a simulated
    ring overwrite via ``floor`` (the oldest still-available absolute index).
    """

    def __init__(self, data_channel_major: np.ndarray, *, floor: int = 0) -> None:
        self._data = np.asarray(data_channel_major, dtype=np.float32)
        self._channels = self._data.shape[0]
        self._total = self._data.shape[1]
        self._floor = floor

    def channels(self) -> int:
        return self._channels

    def head(self) -> int:
        return self._total

    def pull_uv_into(self, cursor: int, out: np.ndarray):
        lost = 0
        if cursor < self._floor:
            lost = self._floor - cursor
            cursor = self._floor
        capacity = out.shape[1]
        avail = self._total - cursor
        n = max(0, min(avail, capacity))
        if n > 0:
            out[:, :n] = self._data[:, cursor : cursor + n]
        return n, cursor + n, lost


class RecordingFactory:
    """An ``outlet_factory`` that remembers the outlet it created.

    Lets a test build an :class:`EmgPublisher` and then inspect what got pushed,
    without reaching into the publisher's private attributes.
    """

    def __init__(self) -> None:
        self.outlet: FakeOutlet | None = None

    def __call__(self, sinfo) -> FakeOutlet:
        self.outlet = FakeOutlet(sinfo)
        return self.outlet


@pytest.fixture
def fake_profile() -> FakeProfile:
    return FakeProfile()
