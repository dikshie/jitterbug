#!/usr/bin/env bash
# Standalone scamper probing script (collects RTT measurements to JSON)
set -euo pipefail

TARGET="${1:-ns4.indosat.com}"
COUNT="${2:-120}"
OUTPUT_JSON="${3:-scamper_ns4_indosat.json}"
INTERVAL="${4:-1}"

echo "=== Probing ${TARGET} (${COUNT} probes, interval: ${INTERVAL}s) ==="
echo "=== Output -> ${OUTPUT_JSON} ==="

sudo scamper \
  -O json \
  -o "${OUTPUT_JSON}" \
  -c "ping -c ${COUNT} -i ${INTERVAL}" \
  -i "${TARGET}"

echo "=== Data collection complete. File saved to: ${OUTPUT_JSON} ==="
echo "To analyze later:"
echo "  uv run jitterbug analyze ${OUTPUT_JSON} --output analysis_results.json"
