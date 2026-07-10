"""EMG publisher: mudraka sEMG samples -> a single LSL float32 outlet."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import numpy as np
from mne_lsl.lsl import StreamInfo, StreamOutlet

log = logging.getLogger("mudra_lsl.publishers.emg")

#: How the provisional scale reaches the outlet metadata. Kept honest: mudraka
#: itself flags 0.035 uV/count as unverified, so we say so rather than letting
#: it look vendor-calibrated.
_SCALE_NOTE_TEMPLATE = (
    "count * {scale} uV/count, inherited from mudraka's StreamProfile.scale. "
    "PROVISIONAL/UNVERIFIED, not vendor-calibrated. Treat as relative amplitude, "
    "not an absolute physical unit, until calibrated."
)

# Factory type for the LSL outlet; overridable in tests with a fake.
OutletFactory = Callable[[StreamInfo], Any]


class EmgPublisher:
    """Drains sEMG samples from a shared ``mudraka.Stream`` and pushes to LSL.

    Owns its own read cursor over the stream, its LSL :class:`StreamOutlet`, and
    a scratch buffer for the channel-major reads. ``poll_and_push`` is safe to
    call at any cadence; it drains everything available since the last call.
    """

    def __init__(
        self,
        stream: Any,
        profile: Any,
        *,
        source_id: str,
        firmware: str | None = None,
        name: str = "MudraEMG",
        stype: str = "EMG",
        max_chunk_samples: int = 2048,
        start_cursor: int | None = None,
        outlet_factory: OutletFactory = StreamOutlet,
    ) -> None:
        self._stream = stream
        self._profile = profile
        self._n_channels = int(profile.channels)

        self._sinfo = self._build_stream_info(
            source_id=source_id, firmware=firmware, name=name, stype=stype
        )
        self._outlet = outlet_factory(self._sinfo)

        # Start from the current head so we publish only samples that arrive
        # after we come up, not whatever historical backlog sits in the ring.
        self._cursor = int(stream.head()) if start_cursor is None else int(start_cursor)

        # Channel-major scratch for pull_uv_into; sample-major buffer for push.
        self._scratch = np.zeros((self._n_channels, max_chunk_samples), dtype=np.float32)
        self._push_buf = np.zeros((max_chunk_samples, self._n_channels), dtype=np.float32)

        self.total_pushed = 0
        self.total_lost = 0

    # -- construction ---------------------------------------------------------

    def _build_stream_info(
        self, *, source_id: str, firmware: str | None, name: str, stype: str
    ) -> StreamInfo:
        # Read metadata off the mudraka profile so a future mudraka bump can't
        # silently desync the LSL description from the wire format.
        channel_names = list(self._profile.channel_names)
        sfreq = float(self._profile.nominal_rate_hz)
        scale = list(self._profile.scale)
        unit = self._profile.unit

        sinfo = StreamInfo(
            name=name,
            stype=stype,
            n_channels=self._n_channels,
            sfreq=sfreq,
            dtype="float32",
            source_id=source_id,
        )
        sinfo.set_channel_names(channel_names)
        sinfo.set_channel_types("emg")
        sinfo.set_channel_units("microvolts")

        # Uniform per-channel scale collapses to a single figure in the note.
        scale_str = str(scale[0]) if len(set(scale)) == 1 else str(scale)
        desc = sinfo.desc
        desc.append_child_value("manufacturer", "Wearable Devices Ltd.")
        desc.append_child_value("device_model", "Mudra Link")
        desc.append_child_value("firmware_version", firmware or "unknown")
        desc.append_child_value("engine", "mudraka")
        desc.append_child_value("unit", unit)
        desc.append_child_value("scale_note", _SCALE_NOTE_TEMPLATE.format(scale=scale_str))

        log.info(
            "EMG outlet '%s' (type=%s) %d ch @ %.1f Hz float32, source_id=%s",
            name,
            stype,
            self._n_channels,
            sfreq,
            source_id,
        )
        return sinfo

    # -- StreamPublisher protocol --------------------------------------------

    def lsl_info(self) -> StreamInfo:
        return self._sinfo

    def poll_and_push(self) -> None:
        capacity = self._scratch.shape[1]
        while True:
            written, cursor, lost = self._stream.pull_uv_into(self._cursor, self._scratch)

            if lost:
                self.total_lost += int(lost)
                log.warning(
                    "EMG ring overwrite: %d samples lost before read (%d total). "
                    "Poll faster or reduce load.",
                    int(lost),
                    self.total_lost,
                )

            # Adopt the authoritative cursor the engine returns (it accounts for
            # any samples skipped due to overwrite).
            if cursor > self._cursor:
                self._cursor = int(cursor)

            if written <= 0:
                break

            # mudraka fills channel-major (n_channels, written); LSL wants
            # sample-major (written, n_channels). Transpose into the contiguous
            # push buffer (an easy silent bug if skipped).
            self._push_buf[:written] = self._scratch[:, :written].T
            self._outlet.push_chunk(self._push_buf[:written])
            self.total_pushed += int(written)

            if written < capacity:
                break  # drained everything currently available

    def close(self) -> None:
        outlet = self._outlet
        self._outlet = None
        if outlet is None:
            return
        closer = getattr(outlet, "close", None)
        if callable(closer):
            closer()
