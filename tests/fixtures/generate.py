"""Regenerate the committed synthetic SNC capture.

Run from the repo root::

    uv run python tests/fixtures/generate.py

Produces ``synthetic_emg_session.jsonl`` next to this file: a deterministic
30-frame (540-sample) synthetic recording used by the offline decode test and as
a template for the JSONL capture format.
"""

from __future__ import annotations

from pathlib import Path

import synth  # local module (tests/fixtures on sys.path when run from here)


def main() -> None:
    session = synth.build_session(n_frames=30, samples_per_frame=18, seed=1)
    out = Path(__file__).parent / "synthetic_emg_session.jsonl"
    synth.write_session_jsonl(session, str(out))
    print(f"wrote {out} ({session.n_samples} samples across {len(session.frames)} frames)")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    main()
