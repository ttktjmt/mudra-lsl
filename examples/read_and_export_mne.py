"""Record a few seconds of the MudraEMG LSL outlet into an MNE ``Raw`` (.fif).

A concrete, runnable check that the outlet's channel metadata (labels, type,
units, rate) survives the round-trip into MNE-Python — the same shape of
analysis (motor-unit decomposition, filtering) this bridge is meant to feed.

Requires the ``examples`` extra (``uv sync --extra examples`` / ``pip install
mudra-lsl[examples]``). Run ``mudra-lsl stream`` first, then::

    uv run python examples/read_and_export_mne.py --duration 10 --output emg_raw.fif
"""

from __future__ import annotations

import argparse
import time

import numpy as np
from mne_lsl.lsl import StreamInlet, resolve_streams


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="MudraEMG", help="LSL stream name to resolve")
    parser.add_argument("--duration", type=float, default=10.0, help="seconds to record")
    parser.add_argument("--output", default="mudra_emg_raw.fif", help="output .fif path")
    parser.add_argument("--resolve-timeout", type=float, default=5.0)
    args = parser.parse_args()

    import mne  # imported lazily so `print_stream.py` works without the extra

    streams = resolve_streams(timeout=args.resolve_timeout, name=args.name)
    if not streams:
        raise SystemExit(f"No {args.name!r} stream found. Is `mudra-lsl stream` running?")
    sinfo = streams[0]
    sfreq = float(sinfo.sfreq)
    ch_names = sinfo.get_channel_names()

    inlet = StreamInlet(sinfo)
    inlet.open_stream()
    print(f"Recording {args.duration:.1f}s from {sinfo.name} ({len(ch_names)} ch @ {sfreq} Hz)...")

    target = int(args.duration * sfreq)
    collected: list[np.ndarray] = []
    n = 0
    deadline = time.monotonic() + args.duration + 5.0  # wall-clock safety margin
    try:
        while n < target and time.monotonic() < deadline:
            data, timestamps = inlet.pull_chunk(timeout=1.0, max_samples=1024)
            if len(timestamps):
                collected.append(np.asarray(data, dtype=np.float64))
                n += len(timestamps)
    finally:
        inlet.close_stream()

    if not collected:
        raise SystemExit("No samples received.")

    # LSL gives sample-major (n_samples, n_channels); MNE wants (n_channels, n_samples).
    samples_uv = np.concatenate(collected, axis=0).T
    # MNE stores EMG in volts. Our values are microvolts on a PROVISIONAL scale
    # (see the stream's scale_note) — converted here for unit-correctness, but
    # treat the amplitude as relative until the scale is calibrated.
    data_volts = samples_uv * 1e-6

    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="emg")
    raw = mne.io.RawArray(data_volts, info)
    raw.save(args.output, overwrite=True)
    print(f"Saved {raw.n_times} samples to {args.output}")


if __name__ == "__main__":
    main()
