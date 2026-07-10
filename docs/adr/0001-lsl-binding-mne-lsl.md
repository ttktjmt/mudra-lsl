# ADR-0001: Use mne-lsl as the LSL binding

- Status: Accepted (2026-07-10)
- Related: ADR-0003, ADR-0004

## Context

There are two main options for publishing an LSL outlet from Python.

- `pylsl` — the official binding, with a track record (`muse-lsl`,
  `OpenBCI_LSL` both use it).
- `mne-lsl` (the `mne_lsl.lsl` module) — the actively maintained successor to
  `pylsl`'s low-level binding. Maintained by FCBG with releases continuing
  through 2026. BSD-3-Clause. Requires Python ≥ 3.11.

`mudra-lsl` anticipates eventually feeding EMG into MNE-Python-based analysis
(e.g. motor-unit decomposition). For a single-outlet EMG bridge, the two
options have no functional difference otherwise.

## Decision

Adopt `mne_lsl.lsl`. Its low-level API (`StreamInfo` / `StreamOutlet` /
`push_chunk`) closely mirrors `pylsl`'s, so migration cost is low. Set
`requires-python = ">=3.11"` in `pyproject.toml` (matches `mne-lsl`'s
requirement; confirmed acceptable).

The following was verified in practice against the installed version
(`mne-lsl 1.13.2`):

- Constructor: `StreamInfo(name, stype, n_channels, sfreq, dtype, source_id)`.
- `set_channel_names` / `set_channel_types` / `set_channel_units` exist and
  round-trip.
- `desc` is a **property** (not a method call), returning an `XMLElement` with
  `append_child_value(name, value)`. The "`desc` vs `desc()`" ambiguity flagged
  in the bootstrap prompt is settled in favor of the property in this version.
- `push_chunk(x, timestamp=None, pushThrough=True)`. `x` must have shape
  `(n_samples, n_channels)`; the reverse shape raises `ValueError` (the basis
  for the transpose requirement in ADR-0004).

## Consequences

- Plugs naturally into the MNE-Python ecosystem.
- Drops support for Python < 3.11. Acceptable for now.
- Pulls in `mne` (via `mne-lsl`) and `scipy` as dependencies. `mne` itself is
  only required by the `examples` extra; the core package runs on `mne-lsl`
  alone.
