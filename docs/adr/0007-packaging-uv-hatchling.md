# ADR-0007: Package with uv + hatchling, flat layout

- Status: Accepted (2026-07-10)
- Related: ADR-0006

## Context

Need to decide the packaging tooling and layout. `mudraka` uses `uv` and ships
a `uv.lock`. `mudra-lsl` should match the family's tooling convention.

## Decision

- Build backend is **hatchling**; dependency/venv management is **uv**. Commit
  `uv.lock` (matching mudraka).
- Package layout is **flat** (`mudra_lsl/` at the repo root), matching the
  bootstrap prompt's §5 structure diagram.
- The public-facing **README lives at the repo root** (the standard location
  GitHub/PyPI expect). §5's diagram showed `docs/README.md`, but the root
  README is treated as authoritative (a minor call within the "decide and
  proceed" latitude of §0.5). ADRs live under `docs/adr/`.
- Provide both a CLI entry point (`mudra-lsl = "mudra_lsl.cli:main"`) and a
  library API (`from mudra_lsl import stream`) — the same dual usage as
  `muse-lsl`.
- Dependency pins:
  - `mudraka>=0.3,<0.4` (latest published is 0.3.1; capped so a future
    breaking mudraka release, e.g. Phase 2's IMU work, doesn't silently change
    behavior).
  - `mne-lsl>=1.6,<2`, `bleak>=0.22`, `numpy>=1.24`.
- Lint with `ruff`, test with `pytest`. Real-device integration tests are
  marked `device` and skipped by default.

## Consequences

- Tooling is consistent across the family; reproducible via `uv sync` /
  `uv run pytest`.
- The PyPI package name `mudra-lsl` was confirmed unclaimed as of 2026-07-10
  (JSON API 404, `pip index` finds no distribution). Re-check immediately
  before the actual first publish (§0.5 category 4).
