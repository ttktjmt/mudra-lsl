"""The minimal publisher seam.

A publisher turns samples drained from a shared ``mudraka.Stream`` into an LSL
outlet. The interface is deliberately tiny — just enough for the orchestrator to
own a list of publishers and tick them — so that Phase 2 (IMU) and Phase 3
(discrete Markers) can slot in without touching the app loop.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mne_lsl.lsl import StreamInfo


@runtime_checkable
class StreamPublisher(Protocol):
    """Everything the orchestrator needs from a publisher."""

    def lsl_info(self) -> StreamInfo:
        """Return the outlet's :class:`StreamInfo` (for logging / inspection)."""
        ...

    def poll_and_push(self) -> None:
        """Drain any samples available since the last call and push them to LSL.

        Called on every tick of the app's poll loop. Must be non-blocking and
        must not raise on recoverable conditions (e.g. ring-buffer overwrite);
        those are logged instead.
        """
        ...

    def close(self) -> None:
        """Release the outlet and any held resources."""
        ...
