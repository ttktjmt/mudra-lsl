"""Synthesize Mudra Link SNC (0xfff4) notification frames for offline tests.

The 16-bit SNC frame layout (from mudraka's ``SNC_PACKET_HYPOTHESIS.md``):

* ``N`` samples x 3 channels x int16 little-endian, per-sample interleaved:
  ``[u0 m0 r0][u1 m1 r1]...`` (channel order: ulnar, median, radial), then
* a trailing ``uint32`` little-endian device timestamp in microseconds.

A retail Mudra Link ships ``N = 18`` samples per notification (112-byte frame),
but decoders derive ``N`` from the payload length rather than hardcoding it, so
this generator is parameterised on ``samples_per_frame`` too.

Nothing here is device- or mudraka-internals specific beyond that documented
wire format; it just lets the tests exercise the real decode + publish path
without hardware.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass

import numpy as np

CHANNELS = 3
NOMINAL_RATE_HZ = 834.0
TRAILER_BYTES = 4


def make_snc_frame(samples: np.ndarray, device_ts_us: int) -> bytes:
    """Build one SNC frame from a ``(n_samples, 3)`` int16 array + a timestamp."""
    samples = np.asarray(samples, dtype="<i2")
    if samples.ndim != 2 or samples.shape[1] != CHANNELS:
        raise ValueError(f"expected (n_samples, {CHANNELS}) int16 array, got {samples.shape}")
    body = samples.tobytes()  # C-order row-major == per-sample interleaved u,m,r
    return body + struct.pack("<I", device_ts_us & 0xFFFFFFFF)


@dataclass
class Session:
    """A synthetic recording: the frames plus the ground-truth samples in them."""

    frames: list[bytes]
    recv_times: list[float]
    #: Ground-truth int16 samples, sample-major ``(n_total, 3)``, ulnar/median/radial.
    samples: np.ndarray

    @property
    def n_samples(self) -> int:
        return self.samples.shape[0]

    def expected_uv(self, scale: float = 0.035) -> np.ndarray:
        """The µV values a correct decode should yield, sample-major float32."""
        return (self.samples.astype(np.float32) * np.float32(scale)).astype(np.float32)


def build_session(
    n_frames: int = 20,
    *,
    samples_per_frame: int = 18,
    start_recv_time: float = 1000.0,
    seed: int = 0,
) -> Session:
    """Build a deterministic synthetic session with varied, signed sample data.

    Each channel gets a distinct sine wave (so values span positive/negative and
    the three channels are distinguishable), quantised to int16.
    """
    n_total = n_frames * samples_per_frame
    idx = np.arange(n_total)
    # Distinct frequency + amplitude per channel; deterministic (no RNG needed,
    # but `seed` nudges the phase so different tests can request different data).
    phases = np.array([0.0, 0.4, 0.8]) + 0.01 * seed
    freqs = np.array([7.0, 11.0, 17.0])  # Hz
    amps = np.array([3000.0, 2200.0, 1500.0])
    samples = np.zeros((n_total, CHANNELS), dtype=np.int16)
    for c in range(CHANNELS):
        wave = amps[c] * np.sin(2 * np.pi * freqs[c] * idx / NOMINAL_RATE_HZ + phases[c])
        samples[:, c] = np.round(wave).astype(np.int16)

    dt_us = round(samples_per_frame / NOMINAL_RATE_HZ * 1e6)
    frames: list[bytes] = []
    recv_times: list[float] = []
    for f in range(n_frames):
        block = samples[f * samples_per_frame : (f + 1) * samples_per_frame]
        frames.append(make_snc_frame(block, device_ts_us=f * dt_us))
        recv_times.append(start_recv_time + f * (samples_per_frame / NOMINAL_RATE_HZ))

    return Session(frames=frames, recv_times=recv_times, samples=samples)


# --- JSONL capture format (mirrors "recorded 0xfff4 session" replay approach) --


def write_session_jsonl(session: Session, path: str) -> None:
    """Serialise a session to newline-delimited JSON: one frame per line."""
    with open(path, "w", encoding="utf-8") as fh:
        for recv_time, frame in zip(session.recv_times, session.frames, strict=True):
            fh.write(json.dumps({"recv_time": recv_time, "data_hex": frame.hex()}) + "\n")


def read_session_jsonl(path: str) -> tuple[list[float], list[bytes]]:
    """Load a JSONL capture back into ``(recv_times, frames)``."""
    recv_times: list[float] = []
    frames: list[bytes] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            recv_times.append(float(record["recv_time"]))
            frames.append(bytes.fromhex(record["data_hex"]))
    return recv_times, frames
