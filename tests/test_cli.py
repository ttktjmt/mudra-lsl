"""Tests for CLI argument parsing (no BLE / no event loop)."""

from __future__ import annotations

import pytest

from mudra_lsl.cli import _build_parser


def test_stream_defaults():
    args = _build_parser().parse_args(["stream"])
    assert args.command == "stream"
    assert args.address is None
    assert args.name_substring == "mudra"
    assert args.stream_name == "MudraEMG"
    assert args.poll_interval == 0.02
    assert args.scan_timeout == 5.0
    assert args.connect_timeout == 30.0
    assert args.duration is None
    assert args.no_reconnect is False
    assert args.max_reconnect_attempts is None
    assert args.forget is False


def test_stream_flags():
    args = _build_parser().parse_args(
        [
            "stream",
            "--address",
            "AA:BB:CC",
            "--forget",
            "--no-reconnect",
            "--duration",
            "5",
            "--poll-interval",
            "0.05",
            "--stream-name",
            "MyEMG",
            "--max-reconnect-attempts",
            "3",
        ]
    )
    assert args.address == "AA:BB:CC"
    assert args.forget is True
    assert args.no_reconnect is True
    assert args.duration == 5.0
    assert args.poll_interval == 0.05
    assert args.stream_name == "MyEMG"
    assert args.max_reconnect_attempts == 3


def test_scan_subcommand():
    args = _build_parser().parse_args(["scan", "--timeout", "3"])
    assert args.command == "scan"
    assert args.timeout == 3.0
    assert args.name_substring == "mudra"


def test_missing_command_errors():
    with pytest.raises(SystemExit):
        _build_parser().parse_args([])


def test_verbose_counts():
    assert _build_parser().parse_args(["-v", "scan"]).verbose == 1
    assert _build_parser().parse_args(["-vv", "scan"]).verbose == 2
