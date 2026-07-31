#!/usr/bin/env bash
# Health checks for FlyPing production (IN-04). No secrets printed.
set -euo pipefail

fail=0
check() {
  local name="$1" url="$2"
  code="$(curl -sS -o /tmp/flyping-hc.body -w '%{http_code}' --max-time 15 "$url" || echo 000)"
  echo "$name HTTP $code"
  if [[ "$code" != "200" ]]; then
    fail=1
  fi
}

check "local_health" "http://127.0.0.1:8080/api/health"
check "local_ready" "http://127.0.0.1:8080/api/ready"
check "app_health" "https://app.flyping.ru/api/health"
check "app_ready" "https://app.flyping.ru/api/ready"
check "api_health" "https://api.flyping.ru/api/health"
check "api_ready" "https://api.flyping.ru/api/ready"
check "landing" "https://flyping.ru/"

if command -v docker >/dev/null; then
  docker ps --filter name=flyping-app --format 'container={{.Names}} status={{.Status}}'
fi

if [[ "$fail" -ne 0 ]]; then
  echo "health-check: FAILED" >&2
  exit 1
fi
echo "health-check: OK"
