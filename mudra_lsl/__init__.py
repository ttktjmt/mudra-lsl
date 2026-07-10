"""mudra-lsl: bridge a Mudra Link wristband's raw sEMG stream to LSL.

Connects to the band over BLE (:mod:`bleak`), decodes the raw sEMG stream with
the published ``mudraka`` engine, and republishes it as a Lab Streaming Layer
outlet via ``mne-lsl``.

Use as a CLI (``mudra-lsl stream``) or as a library::

    import mudra_lsl
    mudra_lsl.stream()              # blocks until Ctrl-C
    mudra_lsl.stream(address="...") # connect directly, skip scanning

For finer control (custom loops, embedding in an async app), construct
:class:`~mudra_lsl.app.MudraLslApp` directly and ``await app.run()``.
"""

from __future__ import annotations

import asyncio
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mudra-lsl")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+dev"

from .app import MudraLslApp
from .publishers import EmgPublisher, StreamPublisher

__all__ = ["MudraLslApp", "EmgPublisher", "StreamPublisher", "stream", "__version__"]


def stream(**kwargs) -> None:
    """Blocking convenience wrapper around :class:`MudraLslApp`.

    Accepts the same keyword arguments as :class:`MudraLslApp` (``address``,
    ``name_substring``, ``poll_interval``, ``duration``, ...). Runs its own
    asyncio event loop and returns when the stream stops (Ctrl-C or ``duration``).
    """
    asyncio.run(MudraLslApp(**kwargs).run())
