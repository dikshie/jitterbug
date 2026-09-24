#!/usr/bin/env bash
# Helper script to run scamper ping with sudo and invoke Jitterbug analysis
set -euo pipefail

TARGET="${1:-ns4.indosat.com}"
COUNT="${2:-120}"
OUTPUT_JSON="${3:-scamper_ns4_indosat.json}"
OUTPUT_ANALYSIS="${4:-analysis_results.json}"

echo "=== Running Scamper Ping for target: ${TARGET} (${COUNT} probes) ==="
sudo scamper -O json -o "${OUTPUT_JSON}" -c "ping -c ${COUNT} -i 1" -i "${TARGET}"

echo "=== Running Jitterbug Analysis on ${OUTPUT_JSON} ==="
uv run jitterbug analyze "${OUTPUT_JSON}" --output "${OUTPUT_ANALYSIS}"

echo "=== Complete. Results saved in ${OUTPUT_ANALYSIS} ==="
