"""Unit tests for scamper helper scripts in tools/."""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Dynamically import scamper_probe and scamper_ping_and_analyze from tools directory
tools_dir = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(tools_dir))

import scamper_ping_and_analyze  # noqa: E402
import scamper_probe  # noqa: E402


class TestScamperProbeResolution:
    def test_resolve_ipv4_literal(self) -> None:
        assert scamper_probe.resolve_target_address("1.1.1.1", ip_version=4) == "1.1.1.1"
        assert scamper_probe.resolve_target_address("1.1.1.1", ip_version=None) == "1.1.1.1"

    def test_resolve_ipv6_literal(self) -> None:
        assert (
            scamper_probe.resolve_target_address("2001:4860:4860::8888", ip_version=6)
            == "2001:4860:4860::8888"
        )
        assert (
            scamper_probe.resolve_target_address("2001:4860:4860::8888", ip_version=None)
            == "2001:4860:4860::8888"
        )

    def test_mismatched_ip_version_raises(self) -> None:
        with pytest.raises(ValueError, match="IPv4, but IPv6 was requested"):
            scamper_probe.resolve_target_address("1.1.1.1", ip_version=6)

        with pytest.raises(ValueError, match="IPv6, but IPv4 was requested"):
            scamper_probe.resolve_target_address("2001:4860:4860::8888", ip_version=4)

    def test_resolve_hostname_ipv4(self) -> None:
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
            ]
            res = scamper_probe.resolve_target_address("example.com", ip_version=4)
            assert res == "93.184.216.34"
            mock_getaddrinfo.assert_called_once_with(
                "example.com", None, family=socket.AF_INET, type=socket.SOCK_STREAM
            )

    def test_resolve_hostname_ipv6(self) -> None:
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (
                    socket.AF_INET6,
                    socket.SOCK_STREAM,
                    6,
                    "",
                    ("2606:2800:220:1:248:1893:25c8:1946", 0),
                )
            ]
            res = scamper_probe.resolve_target_address("example.com", ip_version=6)
            assert res == "2606:2800:220:1:248:1893:25c8:1946"
            mock_getaddrinfo.assert_called_once_with(
                "example.com", None, family=socket.AF_INET6, type=socket.SOCK_STREAM
            )

    def test_resolve_hostname_failure(self) -> None:
        with (
            patch("socket.getaddrinfo", side_effect=socket.gaierror("Name or service not known")),
            pytest.raises(ValueError, match="Failed to resolve IPv4 address"),
        ):
            scamper_probe.resolve_target_address("nonexistent.invalid", ip_version=4)


class TestScamperCommandBuilder:
    def test_build_scamper_command_with_ipv4_and_ipv6(self, tmp_path: Path) -> None:
        out = tmp_path / "out.json"
        with patch("scamper_probe.resolve_scamper", return_value="/usr/bin/scamper"):
            cmd_v4 = scamper_probe.build_scamper_command(
                targets=["1.1.1.1"],
                output_file=out,
                ip_version=4,
            )
            assert "-i" in cmd_v4
            assert cmd_v4[cmd_v4.index("-i") + 1] == "1.1.1.1"

            cmd_v6 = scamper_probe.build_scamper_command(
                targets=["2001:4860:4860::8888"],
                output_file=out,
                ip_version=6,
            )
            assert "-i" in cmd_v6
            assert cmd_v6[cmd_v6.index("-i") + 1] == "2001:4860:4860::8888"


class TestScamperPingAndAnalyzeResolution:
    def test_resolve_target_address(self) -> None:
        assert scamper_ping_and_analyze.resolve_target_address("8.8.8.8", ip_version=4) == "8.8.8.8"
        assert scamper_ping_and_analyze.resolve_target_address("::1", ip_version=6) == "::1"
        with pytest.raises(ValueError, match="IPv4, but IPv6 was requested"):
            scamper_ping_and_analyze.resolve_target_address("8.8.8.8", ip_version=6)


class TestScamperShellScripts:
    def test_probe_target_help(self) -> None:
        script = tools_dir / "probe_target.sh"
        res = subprocess.run(["bash", str(script), "--help"], capture_output=True, text=True)
        assert res.returncode == 0
        assert "-4, --ipv4" in res.stdout
        assert "-6, --ipv6" in res.stdout

    def test_run_scamper_help(self) -> None:
        script = tools_dir / "run_scamper.sh"
        res = subprocess.run(["bash", str(script), "--help"], capture_output=True, text=True)
        assert res.returncode == 0
        assert "-4, --ipv4" in res.stdout
        assert "-6, --ipv6" in res.stdout
