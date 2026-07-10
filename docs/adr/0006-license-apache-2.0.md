# ADR-0006: License the repository under Apache-2.0

- Status: Accepted (2026-07-10)
- Related: ADR-0007

## Context

`mudra-lsl` needs its own OSS license decision. This is **distinct** from
Wearable Devices' RawData license terms and `mudra-lsl`'s standing as a
third-party project (left as a placeholder in the README, deliberately not
written by the agent).

## Decision

Adopt **Apache License 2.0**.

- Place the full canonical Apache-2.0 text as `LICENSE` at the repo root.
- Set `license = "Apache-2.0"` (SPDX form) in `pyproject.toml`'s `[project]`
  table, plus the corresponding Trove classifier (confirmed in practice that
  hatchling accepts both together).
- Dependencies `mne-lsl` (BSD-3-Clause) and `bleak` (MIT-family) are both
  compatible with an Apache-2.0 project depending on them; no special NOTICE
  handling is required.

## Consequences

- Matches `mudraka`'s own license (Apache-2.0) exactly, so no cross-license
  friction arises within the Mudra tooling family.
- The RawData license / third-party positioning language is out of scope for
  this ADR and remains a placeholder in the README pending human confirmation
  with Wearable Devices.
