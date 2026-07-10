# ADR-0003: Leave timestamps to push_chunk's auto-stamping

- Status: Accepted (2026-07-10)
- Related: ADR-0001, `docs/mudraka-wishlist.md`

## Context

Two ways to timestamp samples pushed to the LSL outlet:

1. Call `outlet.push_chunk(samples)` with no explicit timestamp, letting LSL
   auto-stamp (it stamps the chunk's last sample with `local_clock()` and
   back-fills earlier samples at the nominal rate).
2. Compute `t0 + i / 834` explicitly and pass a timestamp array.

`muse-lsl` and `OpenBCI_LSL` both use (1).

## Decision

Adopt (1). Call `push_chunk(samples)` with no explicit timestamp. Simple,
matches community convention, and sufficient for a single EMG bridge.

## Note (important drift from the bootstrap document)

The v1 bootstrap prompt (§2) stated that "mudraka does not yet expose a
per-sample timestamp API." In practice, the installed **mudraka 0.3.1 already
has `Stream.timestamp(sample_index: int) -> float`** (verified directly). This
means the wishlist item from §1.6 ("per-sample timestamp egress") is already
satisfied.

This does not change the v1 decision. The §4 timestamp decision (auto-stamping)
was justified on simplicity/convention grounds, with the existence of a
`ClockModel` assumed as the future escape hatch if higher precision is ever
needed. `Stream.timestamp()` *is* that escape hatch, so it doesn't contradict
the decision. If drift becomes a measured problem in a future session, this API
can be used to move to explicit, higher-precision timestamps (recorded as such
in `docs/mudraka-wishlist.md`).

## Consequences

- Simple to implement. Drift is an accepted, unmeasured risk for now.
- A future, non-breaking migration to explicit timestamps via
  `Stream.timestamp()` remains available.
