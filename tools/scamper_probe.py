#!/usr/bin/env python3
"""
Standalone Scamper RTT Probing Utility.

This script executes CAIDA's `scamper` utility to collect ICMP/UDP/TCP ping
measurements against one or more target hosts and saves the results in
newline-delimited JSON format compatible with Jitterbug's data loader.

Usage:
    # Basic 120-probe collection (1s interval)
    python tools/scamper_probe.py --target ns4.indosat.com --count 120 --output ns4_rtt.json --sudo

    # Continuous collection for a specific duration (e.g., 30 minutes / 1800s)
    python tools/scamper_probe.py --target ns4.indosat.com --duration 1800 --sudo

    # Probing multiple targets
    python tools/scamper_probe.py --target ns4.indosat.com --target 8.8.8.8 --count 60 --sudo
"""

from __future__ import annotations

import argparse
import json
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def resolve_scamper(custom_bin: str = "scamper") -> str:
    """Find scamper executable in PATH or standard system directories."""
    resolved = shutil.which(custom_bin)
    if resolved:
        return resolved

    for candidate in [
        "/opt/local/bin/scamper",
        "/usr/local/bin/scamper",
        "/usr/bin/scamper",
        "/opt/homebrew/bin/scamper",
    ]:
        if Path(candidate).exists():
            return candidate

    raise FileNotFoundError(
        f"scamper binary '{custom_bin}' not found. Please install scamper or specify --scamper-bin."
    )


def build_scamper_command(
    targets: list[str],
    output_file: Path,
    count: int = 120,
    interval: float = 1.0,
    method: str = "icmp-echo",
    payload_size: int | None = None,
    pps: int | None = None,
    use_sudo: bool = False,
    scamper_bin: str = "scamper",
) -> list[str]:
    """Construct the scamper CLI invocation."""
    cmd: list[str] = []
    if use_sudo:
        cmd.append("sudo")

    cmd.append(resolve_scamper(scamper_bin))

    # Output options
    cmd.extend(["-O", "json", "-o", str(output_file)])

    if pps:
        cmd.extend(["-p", str(pps)])

    # Build ping subcommand string
    ping_parts = [f"ping -c {count}", f"-i {interval}", f"-P {method}"]
    if payload_size is not None:
        ping_parts.append(f"-s {payload_size}")

    ping_cmd = " ".join(ping_parts)
    cmd.extend(["-c", ping_cmd])

    # Target addresses
    for t in targets:
        cmd.extend(["-i", t])

    return cmd


def inspect_collected_json(output_file: Path) -> dict[str, Any]:
    """Parse and summarize scamper JSON output file."""
    if not output_file.exists():
        return {"total_lines": 0, "ping_responses": 0, "targets": set()}

    total_lines = 0
    ping_responses = 0
    targets: set[str] = set()
    rtt_values: list[float] = []

    with output_file.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            try:
                data = json.loads(line)
                if data.get("type") == "ping":
                    dst = data.get("dst")
                    if dst:
                        targets.add(dst)
                    for resp in data.get("responses", []):
                        if "rtt" in resp:
                            ping_responses += 1
                            rtt_values.append(float(resp["rtt"]))
            except json.JSONDecodeError:
                continue

    min_rtt = min(rtt_values) if rtt_values else 0.0
    avg_rtt = sum(rtt_values) / len(rtt_values) if rtt_values else 0.0
    max_rtt = max(rtt_values) if rtt_values else 0.0

    return {
        "file_size_bytes": output_file.stat().st_size,
        "total_json_records": total_lines,
        "ping_responses": ping_responses,
        "targets": list(targets),
        "rtt_min_ms": min_rtt,
        "rtt_avg_ms": avg_rtt,
        "rtt_max_ms": max_rtt,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scamper RTT Probing Utility (saves JSON for Jitterbug ingestion)"
    )
    parser.add_argument(
        "--target",
        "-t",
        action="append",
        dest="targets",
        help="Target hostname/IP (can be specified multiple times, default: ns4.indosat.com)",
    )
    parser.add_argument(
        "--target-file",
        "-f",
        type=Path,
        help="Path to file containing one target hostname/IP per line",
    )
    parser.add_argument(
        "--count",
        "-c",
        type=int,
        default=120,
        help="Number of ping probes to send per target (default: 120)",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=1.0,
        help="Interval between probes in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        help="Total collection duration in seconds (overrides --count to duration / interval)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("scamper_ns4_indosat.json"),
        help="Output JSON file path (default: scamper_ns4_indosat.json)",
    )
    parser.add_argument(
        "--method",
        "-m",
        choices=["icmp-echo", "udp-dport", "tcp-syn", "tcp-ack"],
        default="icmp-echo",
        help="Probing method (default: icmp-echo)",
    )
    parser.add_argument(
        "--payload-size",
        "-s",
        type=int,
        default=None,
        help="Probe payload size in bytes (default: 56 for ICMP)",
    )
    parser.add_argument(
        "--pps",
        type=int,
        default=None,
        help="Packets per second limit (default: scamper default)",
    )
    parser.add_argument(
        "--sudo",
        action="store_true",
        help="Execute scamper with sudo (required for raw sockets / BPF access)",
    )
    parser.add_argument(
        "--scamper-bin",
        type=str,
        default="scamper",
        help="Scamper binary name or path (default: scamper)",
    )

    args = parser.parse_args()

    targets: list[str] = args.targets or []
    if args.target_file and args.target_file.exists():
        for line in args.target_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                targets.append(line)

    if not targets:
        targets = ["ns4.indosat.com"]

    count = args.count
    if args.duration:
        count = max(1, int(args.duration / args.interval))

    args.output.parent.mkdir(parents=True, exist_ok=True)

    cmd = build_scamper_command(
        targets=targets,
        output_file=args.output,
        count=count,
        interval=args.interval,
        method=args.method,
        payload_size=args.payload_size,
        pps=args.pps,
        use_sudo=args.sudo,
        scamper_bin=args.scamper_bin,
    )

    print("=" * 60)
    print(" SCAMPER RTT PROBE COLLECTOR")
    print("=" * 60)
    print(f"  Targets        : {', '.join(targets)}")
    print(f"  Probe Count    : {count} per target")
    print(f"  Probe Interval : {args.interval}s")
    print(f"  Probe Method   : {args.method}")
    print(f"  Output File    : {args.output}")
    print(f"  Command        : {' '.join(cmd)}")
    print("=" * 60)
    print("\n[*] Starting probe collection... Press Ctrl+C to stop early.\n")

    start_time = time.time()
    proc = subprocess.Popen(cmd)

    def signal_handler(sig: int, frame: Any) -> None:
        print("\n[!] Received interrupt signal. Terminating scamper cleanly...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    ret_code = proc.wait()
    elapsed = time.time() - start_time

    if ret_code != 0:
        print(f"\n[!] Scamper process exited with return code {ret_code}.")
        if ret_code == 255 and not args.sudo:
            print("[!] If permission was denied (/dev/bpf or raw socket), re-run with --sudo.")
        return ret_code

    print(f"\n[+] Probing completed in {elapsed:.1f} seconds.")

    stats = inspect_collected_json(args.output)
    print("\n" + "=" * 60)
    print(" COLLECTION SUMMARY")
    print("=" * 60)
    print(f"  Output File        : {args.output}")
    print(f"  File Size          : {stats['file_size_bytes']} bytes")
    print(f"  Valid RTT Samples  : {stats['ping_responses']}")
    if stats["ping_responses"] > 0:
        print(
            f"  RTT Min / Avg / Max: {stats['rtt_min_ms']:.2f} / "
            f"{stats['rtt_avg_ms']:.2f} / {stats['rtt_max_ms']:.2f} ms"
        )
    print("=" * 60)
    print("\nTo analyze this dataset later with Jitterbug:")
    print(f"  uv run jitterbug analyze {args.output} --output analysis_results.json")
    print(
        f"  uv run python tools/scamper_ping_and_analyze.py \\\n"
        f"      --output-json {args.output} --analyze-only"
    )
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
