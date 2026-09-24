#!/usr/bin/env python3
"""
Scamper Ping Collection and Jitterbug Congestion Analysis.

This script executes `scamper` to collect ICMP ping measurements against a target
(e.g., ns4.indosat.com), saves the raw output in Scamper JSON format, and feeds
the resulting dataset into Jitterbug for congestion inference.

Usage:
    python tools/scamper_ping_and_analyze.py --target ns4.indosat.com --count 120
    python tools/scamper_ping_and_analyze.py --output-json output.json --analyze-only
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

from jitterbug.analyzer import JitterbugAnalyzer
from jitterbug.models.config import JitterbugConfig


def run_scamper_ping(
    target: str,
    output_json: Path,
    count: int = 120,
    interval: float = 1.0,
    use_sudo: bool = False,
    scamper_bin: str = "scamper",
) -> Path:
    """
    Run scamper ping against a target and save the result as JSON.

    Parameters
    ----------
    target : str
        Target hostname or IP address (e.g., ns4.indosat.com).
    output_json : Path
        Path to save the JSON output file.
    count : int
        Number of ping probes to send.
    interval : float
        Interval between probes in seconds.
    use_sudo : bool
        Whether to invoke scamper with sudo (often required for raw socket / BPF access).
    scamper_bin : str
        Path or command name for the scamper binary.

    Returns
    -------
    Path
        Path to the saved JSON file.
    """
    resolved_scamper = shutil.which(scamper_bin)
    if not resolved_scamper:
        # Check standard MacPorts / Homebrew / system paths
        for candidate in ["/opt/local/bin/scamper", "/usr/local/bin/scamper", "/usr/bin/scamper"]:
            if Path(candidate).exists():
                resolved_scamper = candidate
                break

    if not resolved_scamper:
        raise FileNotFoundError(
            f"scamper binary '{scamper_bin}' not found in PATH or standard system locations."
        )

    # Ensure parent output directory exists
    output_json.parent.mkdir(parents=True, exist_ok=True)

    # Construct scamper command
    cmd: list[str] = []
    if use_sudo:
        cmd.append("sudo")
    cmd.extend(
        [
            resolved_scamper,
            "-O",
            "json",
            "-o",
            str(output_json),
            "-c",
            f"ping -c {count} -i {interval}",
            "-i",
            target,
        ]
    )

    print(f"[*] Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        err_msg = result.stderr.strip() or result.stdout.strip()
        if "could not open /dev/bpf" in err_msg or "Permission denied" in err_msg:
            print("\n[!] Error: Scamper requires elevated permissions for raw sockets / BPF.")
            print(
                f"    Please run with --sudo or execute:\n"
                f"    sudo {' '.join(cmd[1:] if use_sudo else cmd)}\n"
            )
        raise RuntimeError(f"Scamper failed with code {result.returncode}: {err_msg}")

    if not output_json.exists() or output_json.stat().st_size == 0:
        raise RuntimeError(f"Scamper completed but output file {output_json} is empty or missing.")

    file_size = output_json.stat().st_size
    print(f"[+] Scamper measurements successfully saved to: {output_json} ({file_size} bytes)")
    return output_json


def analyze_with_jitterbug(
    json_path: Path,
    algorithm: Literal["ruptures", "bcp"] = "ruptures",
    output_analysis: Path | None = None,
    plot_path: Path | None = None,
) -> dict[str, Any]:
    """
    Feed Scamper JSON output into Jitterbug analyzer.

    Parameters
    ----------
    json_path : Path
        Path to the Scamper JSON file.
    algorithm : Literal["ruptures", "bcp"]
        Change point detection algorithm ('ruptures' or 'bcp').
    output_analysis : Path | None
        Optional path to save full analysis JSON results.
    plot_path : Path | None
        Optional path to save congestion plot PNG.

    Returns
    -------
    dict[str, Any]
        Dictionary representation of CongestionInferenceResult summary.
    """
    print(f"[*] Feeding {json_path} into Jitterbug (algorithm: {algorithm})...")

    config = JitterbugConfig()
    config.change_point_detection.algorithm = algorithm

    analyzer = JitterbugAnalyzer(config=config)
    result = analyzer.analyze_from_file(json_path, file_format="json")

    congested_periods = result.get_congested_periods()
    total_congested_duration = result.get_total_congestion_duration()
    raw_measurements_count = len(analyzer.raw_data.measurements) if analyzer.raw_data else 0
    min_intervals_count = len(analyzer.min_rtt_data.measurements) if analyzer.min_rtt_data else 0

    summary = {
        "raw_measurements": raw_measurements_count,
        "min_rtt_intervals": min_intervals_count,
        "total_inferences": len(result.inferences),
        "congested_periods_detected": len(congested_periods),
        "total_congested_duration_seconds": total_congested_duration,
    }

    print("\n" + "=" * 50)
    print(" JITTERBUG CONGESTION INFERENCE SUMMARY")
    print("=" * 50)
    for k, v in summary.items():
        print(f"  {k.replace('_', ' ').title():<36}: {v}")
    print("=" * 50)

    if congested_periods:
        print("\nCongested Periods:")
        for idx, period in enumerate(congested_periods, 1):
            dur = period.end_epoch - period.start_epoch
            jump_info = (
                f", latency jump: {period.latency_jump.magnitude:.2f}ms"
                if period.latency_jump
                else ""
            )
            print(
                f"  [{idx}] {period.start_timestamp.isoformat()} -> "
                f"{period.end_timestamp.isoformat()} (duration: {dur:.1f}s{jump_info})"
            )
    else:
        print("\nNo congestion periods detected.")

    if output_analysis:
        output_analysis.parent.mkdir(parents=True, exist_ok=True)
        output_analysis.write_text(result.model_dump_json(indent=2))
        print(f"\n[+] Analysis results exported to: {output_analysis}")

    if plot_path:
        try:
            from jitterbug.visualization import JitterbugPlotter

            if analyzer.raw_data and analyzer.min_rtt_data:
                plotter = JitterbugPlotter()
                plot_path.parent.mkdir(parents=True, exist_ok=True)
                plotter.plot_congestion_analysis(
                    raw_data=analyzer.raw_data,
                    min_rtt_data=analyzer.min_rtt_data,
                    results=result,
                    title=f"Congestion Analysis: {json_path.name}",
                    save_path=plot_path,
                )
                print(f"[+] Plot saved to: {plot_path}")
            else:
                print("[!] Skipping plot: raw or minimum RTT data unavailable.")
        except ImportError:
            print("[!] Matplotlib required for plotting (`uv sync --extra visualization`).")

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect RTT data with scamper and run Jitterbug congestion analysis."
    )
    parser.add_argument(
        "--target",
        type=str,
        default="ns4.indosat.com",
        help="Target host to probe (default: ns4.indosat.com)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=120,
        help="Number of ping probes to send (default: 120)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Probe interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("scamper_ns4_indosat.json"),
        help="Path for Scamper output JSON (default: scamper_ns4_indosat.json)",
    )
    parser.add_argument(
        "--output-analysis",
        type=Path,
        default=Path("analysis_results.json"),
        help="Path for Jitterbug analysis output JSON (default: analysis_results.json)",
    )
    parser.add_argument(
        "--plot",
        type=Path,
        default=None,
        help="Path to save visualization plot (e.g. congestion.png)",
    )
    parser.add_argument(
        "--sudo",
        action="store_true",
        help="Run scamper using sudo (required if raw socket permissions needed)",
    )
    parser.add_argument(
        "--scamper-bin",
        type=str,
        default="scamper",
        help="Scamper binary name or path (default: scamper)",
    )
    parser.add_argument(
        "--algorithm",
        type=str,
        choices=["ruptures", "bcp"],
        default="ruptures",
        help="Change point detection algorithm (default: ruptures)",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Skip scamper data collection and only analyze existing --output-json file",
    )

    args = parser.parse_args()

    try:
        if not args.analyze_only:
            run_scamper_ping(
                target=args.target,
                output_json=args.output_json,
                count=args.count,
                interval=args.interval,
                use_sudo=args.sudo,
                scamper_bin=args.scamper_bin,
            )

        analyze_with_jitterbug(
            json_path=args.output_json,
            algorithm=args.algorithm,
            output_analysis=args.output_analysis,
            plot_path=args.plot,
        )
        return 0
    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
