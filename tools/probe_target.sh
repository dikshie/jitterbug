#!/usr/bin/env bash
# Standalone scamper probing script (collects RTT measurements to JSON)
set -euo pipefail

TARGET="ns4.indosat.com"
COUNT="120"
OUTPUT_JSON="scamper_ns4_indosat.json"
INTERVAL="1"
IP_VERSION=""

usage() {
  cat <<EOF
Usage: $0 [options] [TARGET] [COUNT] [OUTPUT_JSON] [INTERVAL]

Options:
  -4, --ipv4           Force IPv4 address resolution
  -6, --ipv6           Force IPv6 address resolution
  -t, --target HOST    Target hostname or IP (default: ns4.indosat.com)
  -c, --count N        Number of ping probes (default: 120)
  -o, --output FILE    Output JSON file (default: scamper_ns4_indosat.json)
  -i, --interval SEC   Interval between probes in seconds (default: 1)
  -h, --help           Show this help message

Examples:
  $0 -4 ns4.indosat.com 120 scamper_ns4.json
  $0 -6 2001:4860:4860::8888 60 google_v6.json
  $0 --ipv4 --target ns4.indosat.com --count 120 --output ns4.json
EOF
  exit 0
}

positional_args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -4|--ipv4)
      IP_VERSION="4"
      shift
      ;;
    -6|--ipv6)
      IP_VERSION="6"
      shift
      ;;
    -t|--target)
      TARGET="$2"
      shift 2
      ;;
    -c|--count)
      COUNT="$2"
      shift 2
      ;;
    -o|--output)
      OUTPUT_JSON="$2"
      shift 2
      ;;
    -i|--interval)
      INTERVAL="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    -*)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
    *)
      positional_args+=("$1")
      shift
      ;;
  esac
done

if [[ ${#positional_args[@]} -ge 1 ]]; then
  TARGET="${positional_args[0]}"
fi
if [[ ${#positional_args[@]} -ge 2 ]]; then
  COUNT="${positional_args[1]}"
fi
if [[ ${#positional_args[@]} -ge 3 ]]; then
  OUTPUT_JSON="${positional_args[2]}"
fi
if [[ ${#positional_args[@]} -ge 4 ]]; then
  INTERVAL="${positional_args[3]}"
fi

RESOLVED_TARGET="${TARGET}"
if [[ -n "${IP_VERSION}" ]]; then
  RESOLVED_TARGET=$(python3 -c "
import ipaddress, socket, sys
target = sys.argv[1]
ip_ver = int(sys.argv[2])
try:
    ip = ipaddress.ip_address(target)
    if ip.version != ip_ver:
        print(f'Error: Target {target} is IPv{ip.version}, but IPv{ip_ver} requested', file=sys.stderr)
        sys.exit(1)
    print(target)
except ValueError:
    family = socket.AF_INET if ip_ver == 4 else socket.AF_INET6
    try:
        addrinfo = socket.getaddrinfo(target, None, family=family)
        print(addrinfo[0][4][0])
    except Exception as e:
        print(f'Error: Could not resolve IPv{ip_ver} address for {target}: {e}', file=sys.stderr)
        sys.exit(1)
" "${TARGET}" "${IP_VERSION}")
fi

IP_LABEL="Default"
if [[ -n "${IP_VERSION}" ]]; then
  IP_LABEL="IPv${IP_VERSION}"
fi

echo "=== Probing ${TARGET} (${RESOLVED_TARGET}) ==="
echo "=== IP Version: ${IP_LABEL} | Probes: ${COUNT} | Interval: ${INTERVAL}s ==="
echo "=== Output -> ${OUTPUT_JSON} ==="

sudo scamper \
  -O json \
  -o "${OUTPUT_JSON}" \
  -c "ping -c ${COUNT} -i ${INTERVAL}" \
  -i "${RESOLVED_TARGET}"

echo "=== Data collection complete. File saved to: ${OUTPUT_JSON} ==="
echo "To analyze later:"
echo "  uv run jitterbug analyze ${OUTPUT_JSON} --output analysis_results.json"

