# Scamper Data Collection & Jitterbug Analysis

This guide explains how to collect Round-Trip Time (RTT) data using **[scamper](https://www.caida.org/catalog/software/scamper/)**, save the output in JSON format, and feed it into **Jitterbug** for network congestion inference.

---

## 1. Overview

[Scamper](https://www.caida.org/catalog/software/scamper/) is an active measurement tool developed by CAIDA that supports high-resolution ICMP, UDP, and TCP ping probing and serializes measurements directly into newline-delimited JSON.

Jitterbug natively ingests scamper's JSON output (`-O json`), extracts transmission timestamps (`tx`) and round-trip times (`rtt`), computes minimum-RTT baselines across time windows, and detects network congestion periods.

---

## 2. Probing Target Only (Save to JSON)

Use [**`tools/scamper_probe.py`**](file:///Users/dikshie/VIRTUAL/jitterbug/tools/scamper_probe.py) or [**`tools/probe_target.sh`**](file:///Users/dikshie/VIRTUAL/jitterbug/tools/probe_target.sh) when you only want to collect RTT data and save it to JSON for later analysis.

### Quick Example: Probe `ns4.indosat.com`

```bash
# Probe ns4.indosat.com for 120 packets (1s interval) and save to JSON
uv run python tools/scamper_probe.py \
  --target ns4.indosat.com \
  --count 120 \
  --output scamper_ns4_indosat.json \
  --sudo
```

Or using the bash script:

```bash
./tools/probe_target.sh ns4.indosat.com 120 scamper_ns4_indosat.json
```

### Advanced Probing Options

#### Duration-Based Collection
Collect continuous RTT data for a set time (e.g. 1 hour / 3600 seconds):
```bash
uv run python tools/scamper_probe.py \
  --target ns4.indosat.com \
  --duration 3600 \
  --interval 1.0 \
  --output ns4_1hour.json \
  --sudo
```

#### Multiple Targets or Target List File
```bash
# Multiple targets on CLI:
uv run python tools/scamper_probe.py \
  --target ns4.indosat.com \
  --target 8.8.8.8 \
  --count 300 \
  --sudo

# From a targets file (one host/IP per line):
uv run python tools/scamper_probe.py \
  --target-file targets.txt \
  --count 300 \
  --output multi_targets.json \
  --sudo
```

#### Probe Methods
Choose between ICMP Echo, UDP, or TCP SYN:
```bash
uv run python tools/scamper_probe.py \
  --target ns4.indosat.com \
  --method icmp-echo \
  --output ns4_icmp.json \
  --sudo
```

---

## 3. Feeding Saved JSON to Jitterbug (Later Analysis)

Once your JSON data has been collected, feed it into Jitterbug at any time.

### Option A: CLI Validation & Analysis

```bash
# 1. Validate dataset format and view sample summary:
uv run jitterbug validate scamper_ns4_indosat.json --verbose

# 2. Run congestion inference and export results:
uv run jitterbug analyze scamper_ns4_indosat.json --output analysis_results.json
```

### Option B: Using `tools/scamper_ping_and_analyze.py` in `--analyze-only` Mode

```bash
uv run python tools/scamper_ping_and_analyze.py \
  --output-json scamper_ns4_indosat.json \
  --analyze-only \
  --plot congestion_plot.png
```

### Option C: Using the Python API

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

# Summary & Congestion periods
print(f"Total inferences: {len(results.inferences)}")
for period in results.get_congested_periods():
    print(
        f"Congested from {period.start_timestamp} to {period.end_timestamp} "
        f"(duration: {period.end_epoch - period.start_epoch:.1f}s)"
    )
```

---

## 4. End-to-End Workflow (Probe + Immediate Analysis)

To probe and immediately analyze in one step:

```bash
uv run python tools/scamper_ping_and_analyze.py \
  --target ns4.indosat.com \
  --count 120 \
  --sudo
```

---

## 5. Summary of Provided Scripts

| Script | Purpose |
|---|---|
| [`tools/scamper_probe.py`](file:///Users/dikshie/VIRTUAL/jitterbug/tools/scamper_probe.py) | **Probing only**: Probes targets (count/duration/method) and saves raw RTT data to JSON. |
| [`tools/probe_target.sh`](file:///Users/dikshie/VIRTUAL/jitterbug/tools/probe_target.sh) | **Probing only (Bash)**: Quick one-liner wrapper for `sudo scamper` saving to JSON. |
| [`tools/scamper_ping_and_analyze.py`](file:///Users/dikshie/VIRTUAL/jitterbug/tools/scamper_ping_and_analyze.py) | **Combined**: Probes target, saves JSON, and runs Jitterbug analysis (also supports `--analyze-only`). |
| [`tools/run_scamper.sh`](file:///Users/dikshie/VIRTUAL/jitterbug/tools/run_scamper.sh) | **Combined (Bash)**: Shell pipeline running `sudo scamper` followed by `jitterbug analyze`. |
