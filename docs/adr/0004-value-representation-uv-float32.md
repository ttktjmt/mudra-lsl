# ADR-0004: Represent values as µV / float32, and mark the scale as provisional

- Status: Accepted (2026-07-10)
- Related: ADR-0001

## Context

Two sample representations are available from mudraka: `int32` (raw counts)
and `float32` (µV-converted), via `latest_into` / `latest_uv_into` and
`pull_into` / `pull_uv_into`. Community convention (`muse-lsl`, `OpenBCI_LSL`,
the MNE-LSL mocks) is `unit=microvolts` / `format=float32`.

However, mudraka's scale value is provisional and unverified. In practice,
`Config().profile.scale == [0.035, 0.035, 0.035]` (a per-channel list), and
mudraka's own documentation explicitly states this is "PROVISIONAL/UNVERIFIED,
not vendor-calibrated."

## Decision

- Publish using `pull_uv_into`, in **float32 / µV**. Channel metadata:
  `type=emg`, `unit=microvolts`.
- Make the provisional nature of the scale explicit **in both the stream
  metadata and the README**. Add a `scale_note` to `desc` stating that
  `0.035 uV/count` is provisional/uncalibrated and should be treated as a
  relative amplitude, not an absolute physical unit.
- Account for the scale being a **per-channel list**, not a single scalar. If
  all channels share one value, render it as a single figure; otherwise render
  the list.
- mudraka's `latest_uv_into` fills channel-major `(n_channels, n_samples)`, but
  `push_chunk` requires sample-major `(n_samples, n_channels)`. **Transpose
  before pushing** (this version of mne-lsl raises `ValueError` on the wrong
  shape, but the transpose is still required to avoid a silent value-swapping
  bug).

## Consequences

- LSL consumers can treat the values as µV without further unit conversion.
- The uncalibrated scale is recorded, reducing the risk of it being misused as
  an absolute value.
- The transpose costs one chunk's worth of memory copy (a few KB) — negligible.
