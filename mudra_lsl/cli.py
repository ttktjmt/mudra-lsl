"""Command-line entry point: ``mudra-lsl stream`` / ``mudra-lsl scan``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from . import __version__, constants
from .app import MudraLslApp
from .ble import scan


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mudra-lsl",
        description=(
            "Stream raw sEMG from a Mudra Link wristband to Lab Streaming Layer (LSL)."
        ),
    )
    parser.add_argument("--version", action="version", version=f"mudra-lsl {__version__}")
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase logging verbosity (-v for INFO, -vv for DEBUG)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    stream = sub.add_parser("stream", help="connect to a band and publish an LSL EMG outlet")
    stream.add_argument(
        "--address",
        default=None,
        help="BLE address/UUID to connect to directly (skip scanning)",
    )
    stream.add_argument(
        "--name-substring",
        default=constants.DEVICE_NAME_SUBSTRING,
        help="case-insensitive substring to match device names when scanning "
        f"(default: {constants.DEVICE_NAME_SUBSTRING!r})",
    )
    stream.add_argument("--adapter", default=None, help="BLE adapter to use (platform-specific)")
    stream.add_argument(
        "--stream-name", default="MudraEMG", help="LSL stream name (default: MudraEMG)"
    )
    stream.add_argument(
        "--poll-interval",
        type=float,
        default=0.02,
        help="seconds between publisher polls (default: 0.02)",
    )
    stream.add_argument(
        "--scan-timeout", type=float, default=5.0, help="BLE scan timeout in seconds (default: 5)"
    )
    stream.add_argument(
        "--connect-timeout",
        type=float,
        default=30.0,
        help="BLE connect timeout in seconds (default: 30)",
    )
    stream.add_argument(
        "--duration",
        type=float,
        default=None,
        help="stop automatically after this many seconds (default: run until Ctrl-C)",
    )
    stream.add_argument(
        "--no-reconnect",
        action="store_true",
        help="do not attempt to reconnect after a dropped link",
    )
    stream.add_argument(
        "--max-reconnect-attempts",
        type=int,
        default=None,
        help="give up after this many failed reconnects (default: retry forever)",
    )
    stream.add_argument(
        "--forget",
        action="store_true",
        help="rescan for a fresh device handle on every (re)connect instead of "
        "reusing a cached one; works around macOS/CoreBluetooth retaining a "
        "stale link after a drop",
    )

    scan_p = sub.add_parser("scan", help="scan for nearby Mudra devices and print them")
    scan_p.add_argument(
        "--name-substring",
        default=constants.DEVICE_NAME_SUBSTRING,
        help=f"substring to match device names (default: {constants.DEVICE_NAME_SUBSTRING!r})",
    )
    scan_p.add_argument("--adapter", default=None, help="BLE adapter to use (platform-specific)")
    scan_p.add_argument(
        "--timeout", type=float, default=5.0, help="scan duration in seconds (default: 5)"
    )

    return parser


def _configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def _run_scan(args: argparse.Namespace) -> int:
    devices = await scan(
        name_substring=args.name_substring, timeout=args.timeout, adapter=args.adapter
    )
    if not devices:
        print(f"No devices matching {args.name_substring!r} found.")
        return 1
    print(f"Found {len(devices)} device(s):")
    for device in devices:
        print(f"  {device.address}  {device.name or '(no name)'}")
    return 0


async def _run_stream(args: argparse.Namespace) -> int:
    app = MudraLslApp(
        address=args.address,
        name_substring=args.name_substring,
        adapter=args.adapter,
        poll_interval=args.poll_interval,
        reconnect=not args.no_reconnect,
        max_reconnect_attempts=args.max_reconnect_attempts,
        forget=args.forget,
        stream_name=args.stream_name,
        scan_timeout=args.scan_timeout,
        connect_timeout=args.connect_timeout,
        duration=args.duration,
    )
    await app.run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    try:
        if args.command == "scan":
            return asyncio.run(_run_scan(args))
        if args.command == "stream":
            return asyncio.run(_run_stream(args))
    except KeyboardInterrupt:
        print("\nInterrupted; shutting down.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - present a clean message, not a traceback
        if args.verbose >= 2:
            raise
        print(f"error: {exc}", file=sys.stderr)
        print("(run with -vv for a full traceback)", file=sys.stderr)
        return 1
    parser.error(f"unknown command: {args.command}")
    return 2  # unreachable; parser.error exits


if __name__ == "__main__":
    raise SystemExit(main())
