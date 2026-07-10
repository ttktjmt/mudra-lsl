# mudraka feature-request wishlist

`mudra-lsl` consumes [`mudraka`](https://github.com/ttktjmt/mudraka) as a
published dependency only and never modifies it. When we hit a signal-support
gap, we record it here as a candidate feature request instead of working around
it.

Each entry is written so it could become a GitHub issue on `ttktjmt/mudraka`
more or less verbatim. **These are drafts** — they have not been filed (this
project's tooling is not authorized to open issues on the mudraka repo). A human
should file or reject them.

> Verified against `mudraka 0.3.1` (installed from PyPI, 2026-07-10).

---

## 1. IMU `IDecoder` (needed for Phase 2)

**Capability.** A decoder for the Mudra Link's IMU stream, analogous to the
existing sEMG (SNC) decoder, exposed through mudraka's `IDecoder` extension
point (named as the intended extension mechanism in mudraka's own `CONTEXT.md`).

**Why mudra-lsl wants it.** Phase 2 of the roadmap adds an IMU LSL publisher.
The agreed path is *mudraka gains an IMU decoder* — not wrapping the vendor
`mudra-sdk` — so `mudra-lsl` can add a second publisher that drains IMU samples
the same way `EmgPublisher` drains EMG.

**Rough interface shape.** Ideally the same shape as the EMG stream so the
publisher seam stays uniform:

- a `Config`/`StreamProfile` describing IMU channels (e.g. accel x/y/z,
  gyro x/y/z), their rate, units, and scale;
- `feed(frame, recv_time)` accepting the IMU characteristic's notification
  payloads (BLE char `0xfff5` / COMMAND-tag `0x70`);
- `pull_*_into` / `latest_*_into` cursor-based readers returning
  `(written, cursor, lost)` like the EMG path.

If IMU and EMG can be driven from one `Stream` with per-modality profiles, even
better; if they need separate `Stream` objects, that is fine too.

---

## 2. Discrete / event decode: gesture, pressure, navigation, button (Phase 3)

**Capability.** Decoding of the COMMAND-channel discrete events (gestures,
pressure, navigation, button) delivered on BLE char `0xfff1`.

**Why mudra-lsl wants it.** Phase 3 adds an LSL irregular-rate **Markers**
stream for these events.

**Open question (for whoever picks up Phase 3 — do not resolve here).** It is
genuinely unclear whether discrete events belong inside mudraka's
ring-buffer/clock model at all. That model is built for *continuous, regularly
sampled* signals; discrete events are sparse and not timed the same way. Two
plausible designs:

- **(a)** mudraka grows an event `IDecoder` that surfaces events with device
  timestamps through a small event-queue API, or
- **(b)** the events are handled by a lightweight parser living entirely inside
  `mudra-lsl`, bypassing mudraka's ring/clock machinery.

Recommendation: decide (a) vs (b) when Phase 3 actually starts, informed by
whether other mudraka consumers also want decoded events. This wishlist just
flags the fork; it does not pick a side.

---

## 3. Per-sample timestamp egress — ALREADY AVAILABLE (0.3.1)

**Status: satisfied.** This was seeded as a nice-to-have ("a
`sample_time(index) -> float` getter over mudraka's internal `ClockModel`"), but
`mudraka 0.3.1` **already exposes** it:

```python
Stream.timestamp(sample_index: int) -> float
```

(The v1 bootstrap document predated this and stated no per-sample timestamp API
existed yet — that is now stale; see ADR-0003.)

`mudra-lsl` v1 deliberately does **not** use it: timestamps are left to LSL's
`push_chunk` auto-stamping (ADR-0003). This entry is retained as a pointer for a
future session that wants higher-precision LSL timestamps than auto-stamping
gives — the building block is already there.

**Possible follow-on asks (not yet needed):**

- A batched variant, e.g. `timestamps_into(from, to, out_f64)`, to avoid a
  Python-level call per sample when stamping a whole chunk.
- Documentation of what clock `timestamp()` is expressed in (device clock vs.
  host `recv_time`-corrected) so a consumer can align it to LSL's `local_clock()`.
