# ADR-0005: The StreamPublisher abstraction, and one device per process

- Status: Accepted (2026-07-10)
- Related: Roadmap (README), ADR-0004

## Context

The roadmap plans IMU for Phase 2 and a discrete-event (gesture/pressure/nav)
Markers stream for Phase 3. Hardcoding v1 as a single script would mean a
rewrite for Phase 2; conversely, building a generic N-signal plugin registry
up front would be over-engineering for signals that don't exist yet.

## Decision

Introduce a minimal `StreamPublisher` seam (`publishers/base.py`):

```python
class StreamPublisher(Protocol):
    def lsl_info(self) -> StreamInfo: ...
    def poll_and_push(self) -> None: ...
    def close(self) -> None: ...
```

- `app.py` owns the BLE connection and a single `mudraka.Stream`. Every
  0xfff4 notification calls `stream.feed(data, recv_time)`; a timer (default
  20 ms) ticks `poll_and_push()` on each publisher. v1's publisher list has
  exactly one entry (`EmgPublisher`), but the loop shape already assumes more.
- `EmgPublisher` owns its own read cursor, LSL outlet, and scratch buffer.
- **One device per process.** Bilateral EMG means running `mudra-lsl` as two
  processes, each disambiguated by its own `source_id` (same model as
  `muse-lsl`).

## Consequences

- Phase 2/3 become "add one publisher class, add one line to `app`'s list" —
  additive, not a rewrite.
- No in-process multi-device support or generic registry is built (non-goal).
- The outlet and publisher persist across reconnects; a BLE drop just shows up
  as a logged gap in samples, not a lost LSL consumer connection.
