#!/usr/bin/env bash
# Watchdog: держит бот+Mini App и HTTPS-туннель живыми.
# Если падает локальный сервис или туннель — перезапускает.
# При новом cloudflare URL обновляет WEBAPP_URL в .env и рестартит бота.
#
# Важно: не долбить *.trycloudflare.com через системный DNS сразу после старта —
# cloudflared печатает URL раньше публикации DNS, а NXDOMAIN кэшируется надолго.
# Готовность туннеля: metrics (ha_connections) + DoH (1.1.1.1), затем curl --resolve.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
LOG_DIR="${LOG_DIR:-/tmp/flypingavia}"
BOT_LOG="$LOG_DIR/bot.log"
TUNNEL_LOG="$LOG_DIR/tunnel.log"
SUPERVISE_LOG="$LOG_DIR/supervise.log"
BOT_PID_FILE="$LOG_DIR/bot.pid"
TUNNEL_PID_FILE="$LOG_DIR/tunnel.pid"
URL_FILE="$LOG_DIR/webapp.url"
METRICS_FILE="$LOG_DIR/tunnel.metrics"

LOCAL_HOST="${LOCAL_HOST:-127.0.0.1}"
LOCAL_PORT="${LOCAL_PORT:-8080}"
CHECK_EVERY="${CHECK_EVERY:-20}"
LOCAL_FAILS_MAX="${LOCAL_FAILS_MAX:-2}"
PUBLIC_FAILS_MAX="${PUBLIC_FAILS_MAX:-3}"
TUNNEL_READY_TIMEOUT="${TUNNEL_READY_TIMEOUT:-120}"
DNS_WAIT_BEFORE_PROBE="${DNS_WAIT_BEFORE_PROBE:-12}"

mkdir -p "$LOG_DIR"
cd "$ROOT"

log() {
  # Только stderr + файл: stdout нужен для URL из start_tunnel (url="$(start_tunnel)").
  local line="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
  printf '%s\n' "$line" | tee -a "$SUPERVISE_LOG" >&2
}

read_env_url() {
  if [[ -f "$ENV_FILE" ]]; then
    grep -E '^WEBAPP_URL=' "$ENV_FILE" | head -n1 | cut -d= -f2- | tr -d '\r' || true
  fi
}

write_env_url() {
  local url="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "WEBAPP_URL=$url" >"$ENV_FILE"
    echo "$url" >"$URL_FILE"
    return
  fi
  if grep -qE '^WEBAPP_URL=' "$ENV_FILE"; then
    sed -i "s|^WEBAPP_URL=.*|WEBAPP_URL=$url|" "$ENV_FILE"
  else
    printf '\nWEBAPP_URL=%s\n' "$url" >>"$ENV_FILE"
  fi
  echo "$url" >"$URL_FILE"
}

pid_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

local_health_ok() {
  curl -sf -m 4 "http://${LOCAL_HOST}:${LOCAL_PORT}/api/health" >/dev/null 2>&1
}

is_cloudflared_cmd() {
  local cmd="$1"
  [[ "$cmd" == cloudflared\ tunnel\ --url* || "$cmd" == */cloudflared\ tunnel\ --url* ]]
}

is_bot_cmd() {
  local cmd="$1"
  [[ "$cmd" == python\ -m\ flypingavia* \
    || "$cmd" == python3\ -m\ flypingavia* \
    || "$cmd" == */python\ -m\ flypingavia* \
    || "$cmd" == */python3\ -m\ flypingavia* ]]
}

stop_pid() {
  local pid_file="$1"
  local name="$2"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if pid_alive "$pid"; then
      log "останавливаю $name pid=$pid"
      kill "$pid" 2>/dev/null || true
      local _
      for _ in $(seq 1 20); do
        pid_alive "$pid" || break
        sleep 0.25
      done
      if pid_alive "$pid"; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
    rm -f "$pid_file"
  fi
}

kill_strays() {
  local pid cmd sig="${1:-TERM}"
  while read -r pid cmd; do
    [[ -z "${pid:-}" ]] && continue
    [[ "$pid" == "$$" || "$pid" == "$PPID" ]] && continue
    if is_cloudflared_cmd "$cmd"; then
      log "kill stray cloudflared pid=$pid ($sig)"
      kill -s "$sig" "$pid" 2>/dev/null || true
    elif is_bot_cmd "$cmd"; then
      log "kill stray bot pid=$pid ($sig)"
      kill -s "$sig" "$pid" 2>/dev/null || true
    fi
  done < <(ps -eo pid=,args=)
}

kill_cloudflared_strays() {
  local pid cmd sig="${1:-TERM}"
  while read -r pid cmd; do
    [[ -z "${pid:-}" ]] && continue
    [[ "$pid" == "$$" || "$pid" == "$PPID" ]] && continue
    if is_cloudflared_cmd "$cmd"; then
      log "kill stray cloudflared pid=$pid ($sig)"
      kill -s "$sig" "$pid" 2>/dev/null || true
    fi
  done < <(ps -eo pid=,args=)
}

tunnel_metrics_port() {
  # "Starting metrics server on 127.0.0.1:PORT/metrics"
  grep -Eo 'Starting metrics server on 127\.0\.0\.1:[0-9]+' "$TUNNEL_LOG" 2>/dev/null \
    | tail -n1 | grep -Eo '[0-9]+$' || true
}

tunnel_ha_ok() {
  local port
  port="$(tunnel_metrics_port)"
  [[ -n "$port" ]] || return 1
  local body
  body="$(curl -sf -m 3 "http://127.0.0.1:${port}/metrics" 2>/dev/null || true)"
  [[ -n "$body" ]] || return 1
  echo "$body" >"$METRICS_FILE"
  local ha
  ha="$(echo "$body" | awk '/^cloudflared_tunnel_ha_connections / {print $2; exit}')"
  [[ -n "$ha" ]] || return 1
  awk -v n="$ha" 'BEGIN { exit !(n+0 >= 1) }'
}

# DoH A-запись через IP Cloudflare — не трогает системный резолвер.
doh_resolve_a() {
  local host="$1"
  curl -sf -m 5 "https://1.1.1.1/dns-query?name=${host}&type=A" \
    -H 'accept: application/dns-json' 2>/dev/null \
    | python3 -c 'import json,sys
d=json.load(sys.stdin)
for a in d.get("Answer") or []:
  if a.get("type")==1:
    print(a["data"]); break
' 2>/dev/null || true
}

public_health_ok() {
  local url="${1:-}"
  [[ -n "$url" ]] || return 1
  local host path
  host="$(python3 -c 'import sys; from urllib.parse import urlparse; print(urlparse(sys.argv[1]).hostname or "")' "$url")"
  [[ -n "$host" ]] || return 1

  local ip
  ip="$(doh_resolve_a "$host")"
  [[ -n "$ip" ]] || return 1

  # curl --resolve обходит системный DNS (не травит NXDOMAIN-кэш)
  curl -sf -m 12 --resolve "${host}:443:${ip}" "${url%/}/api/health" >/dev/null 2>&1
}

start_bot() {
  stop_pid "$BOT_PID_FILE" "bot"
  log "запускаю бота (python -m flypingavia)"
  (
    cd "$ROOT"
    export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
    nohup python3 -m flypingavia >>"$BOT_LOG" 2>&1 &
    echo $! >"$BOT_PID_FILE"
  )
  local i
  for i in $(seq 1 40); do
    if local_health_ok; then
      log "бот готов (local health ok)"
      return 0
    fi
    sleep 0.5
  done
  log "ERROR: бот не ответил на /api/health"
  return 1
}

extract_tunnel_url() {
  grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | tail -n1 || true
}

start_tunnel() {
  stop_pid "$TUNNEL_PID_FILE" "tunnel"
  kill_cloudflared_strays TERM
  sleep 0.5
  kill_cloudflared_strays KILL
  sleep 0.3
  : >"$TUNNEL_LOG"
  rm -f "$METRICS_FILE"
  log "запускаю cloudflared → http://${LOCAL_HOST}:${LOCAL_PORT}"
  nohup cloudflared tunnel --url "http://${LOCAL_HOST}:${LOCAL_PORT}" \
    --no-autoupdate >>"$TUNNEL_LOG" 2>&1 &
  echo $! >"$TUNNEL_PID_FILE"

  local url="" i ha_ok=0 dns_ok=0 http_ok=0 url_seen_at=0
  for i in $(seq 1 "$TUNNEL_READY_TIMEOUT"); do
    if ! pid_alive "$(cat "$TUNNEL_PID_FILE" 2>/dev/null || true)"; then
      log "ERROR: cloudflared умер при старте"
      return 1
    fi

    url="$(extract_tunnel_url)"
    if [[ -n "$url" && "$url_seen_at" -eq 0 ]]; then
      url_seen_at=$i
      log "получен URL туннеля: $url (ждём DNS ≥${DNS_WAIT_BEFORE_PROBE}s + ha_connections)"
    fi

    if tunnel_ha_ok; then
      ha_ok=1
    fi

    if [[ -n "$url" && $((i - url_seen_at)) -ge $DNS_WAIT_BEFORE_PROBE ]]; then
      local host
      host="$(python3 -c 'import sys; from urllib.parse import urlparse; print(urlparse(sys.argv[1]).hostname or "")' "$url")"
      if [[ -n "$(doh_resolve_a "$host")" ]]; then
        dns_ok=1
        if public_health_ok "$url"; then
          http_ok=1
          log "туннель готов: $url (ha=$ha_ok dns=1 http=1)"
          echo "$url"
          return 0
        fi
      fi
    fi

    if (( i % 15 == 0 )); then
      log "ожидание туннеля… url=${url:-none} ha=$ha_ok dns=$dns_ok http=$http_ok"
    fi
    sleep 1
  done

  # Если edge зарегистрирован и URL есть — отдаём даже без http-проверки
  # (Telegram резолвит DNS сам; системный кэш здесь может врать).
  url="$(extract_tunnel_url)"
  if [[ -n "$url" ]] && tunnel_ha_ok; then
    log "WARN: отдаём URL при ha_connections>=1 без подтверждённого http: $url"
    echo "$url"
    return 0
  fi
  if [[ -n "$url" ]]; then
    log "WARN: отдаём URL без ha/http: $url"
    echo "$url"
    return 0
  fi
  log "ERROR: не удалось получить URL туннеля"
  return 1
}

ensure_url_synced() {
  local url="$1"
  local current
  current="$(read_env_url)"
  if [[ "$current" != "$url" ]]; then
    log "обновляю WEBAPP_URL: ${current:-<empty>} → $url"
    write_env_url "$url"
    start_bot
  else
    write_env_url "$url"
  fi
}

restart_stack() {
  log "полный рестарт стека"
  local url
  if ! start_bot; then
    log "ERROR: бот не поднялся"
    return 1
  fi
  if ! url="$(start_tunnel)"; then
    log "ERROR: туннель не поднялся"
    return 1
  fi
  ensure_url_synced "$url"
  log "стек поднят: $url"
}

cleanup() {
  log "supervise останавливается (signal)"
  stop_pid "$TUNNEL_PID_FILE" "tunnel"
  stop_pid "$BOT_PID_FILE" "bot"
  exit 0
}

trap cleanup INT TERM

log "=== supervise start root=$ROOT ==="
kill_strays TERM
sleep 1
kill_strays KILL
sleep 1
restart_stack || true

local_fails=0
public_fails=0

while true; do
  sleep "$CHECK_EVERY"

  bot_pid="$(cat "$BOT_PID_FILE" 2>/dev/null || true)"
  if ! pid_alive "$bot_pid" || ! local_health_ok; then
    local_fails=$((local_fails + 1))
    log "local health fail ($local_fails/$LOCAL_FAILS_MAX) pid=${bot_pid:-none}"
    if (( local_fails >= LOCAL_FAILS_MAX )); then
      start_bot || true
      local_fails=0
    fi
  else
    local_fails=0
  fi

  tunnel_pid="$(cat "$TUNNEL_PID_FILE" 2>/dev/null || true)"
  url="$(read_env_url)"
  fresh="$(extract_tunnel_url)"
  if [[ -n "$fresh" && -n "$url" && "$fresh" != "$url" ]]; then
    log "в логе туннеля новый URL: $fresh"
    ensure_url_synced "$fresh"
    url="$fresh"
    public_fails=0
    continue
  fi

  need_tunnel_restart=0
  if ! pid_alive "$tunnel_pid"; then
    log "cloudflared не жив"
    need_tunnel_restart=1
  elif ! tunnel_ha_ok; then
    public_fails=$((public_fails + 1))
    log "tunnel ha_connections fail ($public_fails/$PUBLIC_FAILS_MAX)"
    if (( public_fails >= PUBLIC_FAILS_MAX )); then
      need_tunnel_restart=1
    fi
  elif ! public_health_ok "$url"; then
    # DNS/HTTP через DoH; одна ошибка не рестартит сразу
    public_fails=$((public_fails + 1))
    log "public health fail ($public_fails/$PUBLIC_FAILS_MAX) url=${url:-none}"
    if (( public_fails >= PUBLIC_FAILS_MAX )); then
      need_tunnel_restart=1
    fi
  else
    public_fails=0
  fi

  if (( need_tunnel_restart == 1 )); then
    if ! local_health_ok; then
      start_bot || true
    fi
    if new_url="$(start_tunnel)"; then
      ensure_url_synced "$new_url"
      public_fails=0
    else
      log "ERROR: не удалось перезапустить туннель, повторю через цикл"
    fi
  fi
done
