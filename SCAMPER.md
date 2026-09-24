# Scamper Data Collection & Jitterbug Analysis

This guide explains how to collect Round-Trip Time (RTT) data using **[scamper](https://www.caida.org/catalog/software/scamper/)**, save the output in JSON format, and feed it into **Jitterbug** for network congestion inference.

---

## 1. Overview

[Scamper](https://www.caida.org/catalog/software/scamper/) is a network measurement tool developed by CAIDA that supports active ping probing and can serialize measurements directly into newline-delimited JSON.

Jitterbug natively ingests scamper's JSON output (`-O json`), extracts transmission timestamps (`tx`) and round-trip times (`rtt`), computes minimum-RTT baselines across time windows, and detects network congestion periods.

---

## 2. Quick Start

### Target Example: `ns4.indosat.com`

To probe `ns4.indosat.com` (120 probes at 1-second intervals) and immediately run Jitterbug congestion analysis:

```bash
# Using the integrated Python utility (recommended)
uv run python tools/scamper_ping_and_analyze.py --target ns4.indosat.com --count 120 --sudo
```

Or using the shell helper:

```bash
./tools/run_scamper.sh ns4.indosat.com 120 scamper_ns4_indosat.json analysis_results.json
```

---

## 3. Manual Step-by-Step Workflow

### Step 1: Run Scamper and Save Output to JSON

Run `scamper` with `-O json` to output JSON lines and specify the output file using `-o`:

```bash
sudo scamper \
  -O json \
  -o scamper_ns4_indosat.json \
  -c "ping -c 120 -i 1" \
  -i ns4.indosat.com
```

> **Note on Permissions:**
> On macOS (`/dev/bpf*`) and Linux (raw sockets), ICMP ping via `scamper` typically requires elevated privileges (`sudo`).

### Scamper JSON Structure

The output file contains JSON lines formatted as:

```json
{"type":"ping","src":"192.168.1.50","dst":"202.155.0.25","responses":[{"rtt":18.421,"tx":{"sec":1758700000,"usec":123456}}]}
```

- Each valid response provides an `rtt` (in milliseconds) and transmission time `tx` (`sec` + `usec` converted to epoch seconds).
- Timeouts and non-ping records are automatically filtered by Jitterbug's loader.

---

### Step 2: Feed JSON to Jitterbug

#### Option A: Using the Jitterbug CLI

Validate the collected dataset:
```bash
uv run jitterbug validate scamper_ns4_indosat.json --verbose
```

Run congestion analysis:
```bash
uv run jitterbug analyze scamper_ns4_indosat.json --output analysis_results.json
```

#### Option B: Using the Python API

```python
from pathlib import Path
from jitterbug.analyzer import JitterbugAnalyzer
from jitterbug.models.config import JitterbugConfig

# Configure analyzer
config = JitterbugConfig()
config.change_point_detection.algorithm = "ruptures"

analyzer = JitterbugAnalyzer(config=config)

# Load and analyze scamper JSON file
results = analyzer.analyze_from_file(Path("scamper_ns4_indosat.json"), file_format="json")

# Inspect results
print(f"Total inferences: {len(results.inferences)}")
for period in results.get_congested_periods():
    print(
        f"Congested from {period.start_timestamp} to {period.end_timestamp} "
        f"(duration: {period.end_epoch - period.start_epoch:.1f}s)"
    )
```

---

## 4. Script Reference: `tools/scamper_ping_and_analyze.py`

The repository includes a dedicated tool script [**`tools/scamper_ping_and_analyze.py`**](file:///Users/dikshie/VIRTUAL/jitterbug/tools/scamper_ping_and_analyze.py).

### Command-Line Arguments

| Flag | Default | Description |
|---|---|---|
| `--target` | `ns4.indosat.com` | Target hostname or IP address |
| `--count` | `120` | Number of ICMP probes to transmit |
| `--interval` | `1.0` | Delay between probes in seconds |
| `--output-json` | `scamper_ns4_indosat.json` | Path to save the raw Scamper JSON |
| `--output-analysis` | `analysis_results.json` | Path to save Jitterbug inference JSON |
| `--plot` | `None` | Optional path to export plot (e.g. `plot.png`) |
| `--sudo` | `False` | Run scamper with `sudo` |
| `--algorithm` | `ruptures` | Detection algorithm (`ruptures` or `bcp`) |
| `--analyze-only` | `False` | Skip probing and analyze an existing JSON file |

### Example: Analyze Existing File Only

```bash
uv run python tools/scamper_ping_and_analyze.py \
  --output-json scamper_ns4_indosat.json \
  --analyze-only \
  --plot congestion_plot.png
```
