"""End-to-end offline test: synthetic BLE frames -> real mudraka -> LSL push.

This is the CI-friendly integration tier from the test plan: recorded/synthetic
0xfff4 frames are fed, in order, through a *real* ``mudraka.Stream``, and the
EmgPublisher drains them into a fake outlet. It proves the whole decode + scale
+ transpose + push path is correct, without any BLE device or LSL network.
"""

from __future__ import annotations

import mudraka
import numpy as np
from conftest import RecordingFactory
from fixtures import synth

from mudra_lsl.publishers.emg import EmgPublisher


def _publisher_over(
    stream: mudraka.Stream, cfg: mudraka.Config
) -> tuple[EmgPublisher, RecordingFactory]:
    factory = RecordingFactory()
    pub = EmgPublisher(
        stream,
        cfg.profile,
        source_id="7000042",
        firmware="1.0.0",
        start_cursor=0,
        outlet_factory=factory,
    )
    return pub, factory


def test_feed_all_then_drain_matches_expected_uv():
    session = synth.build_session(n_frames=25, samples_per_frame=18)
    cfg = mudraka.Config()
    stream = mudraka.Stream(cfg)
    pub, factory = _publisher_over(stream, cfg)

    for recv_time, frame in zip(session.recv_times, session.frames, strict=True):
        assert stream.feed(frame, recv_time) == 18
    pub.poll_and_push()

    out = factory.outlet.all_samples
    assert out.shape == (session.n_samples, 3)
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, session.expected_uv(), rtol=1e-4, atol=1e-3)
    assert pub.total_lost == 0


def test_interleaved_feed_and_poll_matches_expected_uv():
    # Realistic cadence: poll after every notification, like the app loop.
    session = synth.build_session(n_frames=25, samples_per_frame=18, seed=3)
    cfg = mudraka.Config()
    stream = mudraka.Stream(cfg)
    pub, factory = _publisher_over(stream, cfg)

    for recv_time, frame in zip(session.recv_times, session.frames, strict=True):
        stream.feed(frame, recv_time)
        pub.poll_and_push()

    out = factory.outlet.all_samples
    assert out.shape == (session.n_samples, 3)
    np.testing.assert_allclose(out, session.expected_uv(), rtol=1e-4, atol=1e-3)


def test_variable_samples_per_frame_are_derived_not_hardcoded():
    # mudraka derives sample count from payload length; a non-18 frame must work.
    session = synth.build_session(n_frames=5, samples_per_frame=12)
    cfg = mudraka.Config()
    stream = mudraka.Stream(cfg)
    pub, factory = _publisher_over(stream, cfg)

    for recv_time, frame in zip(session.recv_times, session.frames, strict=True):
        assert stream.feed(frame, recv_time) == 12
    pub.poll_and_push()

    np.testing.assert_allclose(
        factory.outlet.all_samples, session.expected_uv(), rtol=1e-4, atol=1e-3
    )


def test_jsonl_capture_roundtrips_through_decode(tmp_path):
    session = synth.build_session(n_frames=10)
    path = tmp_path / "capture.jsonl"
    synth.write_session_jsonl(session, str(path))

    recv_times, frames = synth.read_session_jsonl(str(path))
    cfg = mudraka.Config()
    stream = mudraka.Stream(cfg)
    pub, factory = _publisher_over(stream, cfg)
    for recv_time, frame in zip(recv_times, frames, strict=True):
        stream.feed(frame, recv_time)
    pub.poll_and_push()

    np.testing.assert_allclose(
        factory.outlet.all_samples, session.expected_uv(), rtol=1e-4, atol=1e-3
    )


def test_committed_fixture_decodes_to_expected_sample_count():
    # The committed synthetic capture stays loadable/decodable as a regression
    # guard on the frame format and the JSONL loader.
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "synthetic_emg_session.jsonl"
    recv_times, frames = synth.read_session_jsonl(str(fixture))
    assert len(frames) > 0

    cfg = mudraka.Config()
    stream = mudraka.Stream(cfg)
    pub, factory = _publisher_over(stream, cfg)
    for recv_time, frame in zip(recv_times, frames, strict=True):
        stream.feed(frame, recv_time)
    pub.poll_and_push()

    total = factory.outlet.all_samples.shape[0]
    assert total == pub.total_pushed
    assert total == stream.head()
    # sanity: µV values are finite and in a plausible range for the synthetic set
    assert np.all(np.isfinite(factory.outlet.all_samples))
    assert np.abs(factory.outlet.all_samples).max() < 1000.0
