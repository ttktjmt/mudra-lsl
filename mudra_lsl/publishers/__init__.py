"""LSL publishers: one per signal modality.

v1 ships only :class:`~mudra_lsl.publishers.emg.EmgPublisher`. The
:class:`~mudra_lsl.publishers.base.StreamPublisher` seam exists so a future IMU
or Markers publisher is an additive change (one class, one line in the app), not
a rewrite.
"""

from .base import StreamPublisher
from .emg import EmgPublisher

__all__ = ["StreamPublisher", "EmgPublisher"]
