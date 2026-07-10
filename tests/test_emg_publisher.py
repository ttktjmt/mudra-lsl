"""Unit tests for EmgPublisher against fake stream/outlet (no mudraka, no LSL net)."""

from __future__ import annotations

import logging

import numpy as np
from conftest import FakeProfile, FakeStream, RecordingFactory

from mudra_lsl.publishers.emg import EmgPublisher


def make_publisher(
    data_channel_major: np.ndarray,
    *,
    floor: int = 0,
    profile: FakeProfile | None = None,
    max_chunk_samples: int = 2048,
    start_cursor: int | None = 0,
    source_id: str = "7000042",
    firmware: str | None = "1.2.3",
) -> tuple[EmgPublisher, FakeStream, RecordingFactory]:
    profile = profile or FakeProfile()
    stream = FakeStream(data_channel_major, floor=floor)
    factory = RecordingFactory()
    pub = EmgPublisher(
        stream,
        profile,
        source_id=source_id,
        firmware=firmware,
        max_chunk_samples=max_chunk_samples,
        start_cursor=start_cursor,
        outlet_factory=factory,
    )
    return pub, stream, factory


def ramp(n: int) -> np.ndarray:
    """Channel-major (3, n) data where each channel has distinct values."""
    return np.vstack([np.arange(n) * 1.0, np.arange(n) * 10.0, np.arange(n) * 100.0]).astype(
        np.float32
    )


# -- StreamInfo metadata -------------------------------------------------------


def test_stream_info_metadata():
    pub, _, _ = make_publisher(np.zeros((3, 0), dtype=np.float32), source_id="7000042")
    info = pub.lsl_info()

    assert info.name == "MudraEMG"
    assert info.stype == "EMG"
    assert info.n_channels == 3
    assert info.sfreq == 834.0
    assert np.dtype(info.dtype) == np.dtype("float32")
    assert info.source_id == "7000042"
    assert info.get_channel_names() == ["ulnar", "median", "radial"]
    assert info.get_channel_types() == ["emg", "emg", "emg"]
    assert info.get_channel_units() == ["microvolts", "microvolts", "microvolts"]


def test_stream_info_desc_carries_provenance_and_scale_caveat():
    pub, _, _ = make_publisher(np.zeros((3, 0), dtype=np.float32), firmware="9.9.9")
    xml = pub.lsl_info().as_xml

    assert "Wearable Devices Ltd." in xml
    assert "Mudra Link" in xml
    assert "9.9.9" in xml
    assert "0.035" in xml
    # The scale must be advertised as provisional, not vendor-calibrated.
    assert "PROVISIONAL" in xml


# -- draining / transpose correctness -----------------------------------------


def test_poll_pushes_transposed_microvolts():
    n = 50
    data = ramp(n)
    pub, _, factory = make_publisher(data, start_cursor=0)

    pub.poll_and_push()

    out = factory.outlet.all_samples
    assert out.shape == (n, 3)  # sample-major
    assert out.dtype == np.float32
    # Column c of the sample-major output must equal channel c of the source:
    # this is the transpose that would be a silent data-scrambling bug if wrong.
    np.testing.assert_allclose(out[:, 0], data[0])
    np.testing.assert_allclose(out[:, 1], data[1])
    np.testing.assert_allclose(out[:, 2], data[2])
    assert pub.total_pushed == n
    assert pub.total_lost == 0


def test_drains_in_multiple_rounds_when_backlog_exceeds_buffer():
    n = 10
    data = np.tile(np.arange(n, dtype=np.float32), (3, 1))
    pub, _, factory = make_publisher(data, max_chunk_samples=4, start_cursor=0)

    pub.poll_and_push()

    assert pub.total_pushed == 10
    assert [c.shape[0] for c in factory.outlet.chunks] == [4, 4, 2]
    np.testing.assert_allclose(factory.outlet.all_samples[:, 0], data[0])


def test_default_cursor_starts_at_head_so_no_backlog_replay():
    data = np.tile(np.arange(30, dtype=np.float32), (3, 1))
    # start_cursor=None -> publisher should start at head() == 30, pushing nothing.
    pub, _, factory = make_publisher(data, start_cursor=None)

    pub.poll_and_push()

    assert pub.total_pushed == 0
    assert factory.outlet.all_samples.shape == (0, 3)


def test_idempotent_when_no_new_samples():
    data = ramp(20)
    pub, _, factory = make_publisher(data, start_cursor=0)

    pub.poll_and_push()
    pushed_first = pub.total_pushed
    pub.poll_and_push()  # nothing new

    assert pub.total_pushed == pushed_first == 20


# -- lost / ring overwrite -----------------------------------------------------


def test_ring_overwrite_reports_lost_and_skips_gap(caplog):
    n = 30
    data = np.tile(np.arange(n, dtype=np.float32), (3, 1))
    # Samples [0, 20) were overwritten before we could read them.
    pub, _, factory = make_publisher(data, floor=20, start_cursor=0)

    with caplog.at_level(logging.WARNING):
        pub.poll_and_push()

    assert pub.total_lost == 20
    assert pub.total_pushed == 10  # only [20, 30) survived
    assert any("lost" in r.getMessage().lower() for r in caplog.records)
    # The surviving samples are the tail of the source, in order.
    np.testing.assert_allclose(factory.outlet.all_samples[:, 0], data[0, 20:30])


# -- lifecycle -----------------------------------------------------------------


def test_close_closes_outlet():
    pub, _, factory = make_publisher(np.zeros((3, 0), dtype=np.float32))
    pub.close()
    assert factory.outlet.closed is True


def test_close_is_idempotent():
    pub, _, _ = make_publisher(np.zeros((3, 0), dtype=np.float32))
    pub.close()
    pub.close()  # must not raise


def test_reused_push_buffer_does_not_corrupt_earlier_chunks():
    # Two poll rounds with different data; the second must not retro-mutate the
    # first recorded chunk (guards the buffer-reuse + copy contract).
    data = ramp(4)
    stream = FakeStream(data, floor=0)
    factory = RecordingFactory()
    pub = EmgPublisher(
        stream,
        FakeProfile(),
        source_id="1",
        max_chunk_samples=2,
        start_cursor=0,
        outlet_factory=factory,
    )
    pub.poll_and_push()
    first_chunk = factory.outlet.chunks[0].copy()
    # all chunks already pushed; assert first chunk is still its original value
    np.testing.assert_allclose(factory.outlet.chunks[0], first_chunk)
    assert pub.total_pushed == 4
