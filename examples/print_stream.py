"""Resolve the MudraEMG LSL outlet and print incoming chunks.

A minimal, dependency-light proof that the outlet is well-formed and flowing.

Run ``mudra-lsl stream`` in one terminal, then in another::

    uv run python examples/print_stream.py
"""

from __future__ import annotations

import argparse
import time

from mne_lsl.lsl import StreamInlet, resolve_streams


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="MudraEMG", help="LSL stream name to resolve")
    parser.add_argument("--resolve-timeout", type=float, default=5.0)
    args = parser.parse_args()

    print(f"Resolving LSL stream {args.name!r} ...")
    streams = resolve_streams(timeout=args.resolve_timeout, name=args.name)
    if not streams:
        raise SystemExit(f"No {args.name!r} stream found. Is `mudra-lsl stream` running?")

    sinfo = streams[0]
    print(
        f"Found {sinfo.name} (type={sinfo.stype}) "
        f"{sinfo.n_channels} ch @ {sinfo.sfreq} Hz, source_id={sinfo.source_id}"
    )
    print("channels:", sinfo.get_channel_names(), sinfo.get_channel_units())

    inlet = StreamInlet(sinfo)
    inlet.open_stream()
    print("Streaming; press Ctrl-C to stop.")
    try:
        while True:
            data, timestamps = inlet.pull_chunk(timeout=1.0, max_samples=256)
            if len(timestamps):
                print(f"{len(timestamps):4d} samples  latest_uV={data[-1]}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        inlet.close_stream()


if __name__ == "__main__":
    main()
