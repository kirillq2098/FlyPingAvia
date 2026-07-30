#!/usr/bin/env bash
# Watchdog: держит бот+Mini App живыми.
#
# APP_ENV=production (или SUPERVISE_MODE=production / USE_TEMP_TUNNEL=0):
#   - требует постоянный WEBAPP_URL в .env (HTTPS)
#   - НЕ запускает temporary trycloudflare tunnel
#   - НЕ переписывает WEBAPP_URL
#   - проверяет local /api/health (и опционально public WEBAPP_URL/api/ready)
#
# development (по умолчанию):
#   - quick tunnel cloudflared --url (ephemeral)
#   - при новом URL обновляет WEBAPP_URL и рестартит бота
#
# Named tunnel / VPS+домен: см. deploy/ и docs.
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

read_env_var() {
  local key="$1"
  if [[ -f "$ENV_FILE" ]]; then
    grep -E "^${key}=" "$ENV_FILE" | head -n1 | cut -d= -f2- | tr -d '\r' || true
  fi
}

read_env_url() {
  read_env_var WEBAPP_URL
}

read_app_env() {
  local v
  v="$(read_env_var APP_ENV)"
  echo "${v:-development}" | tr '[:upper:]' '[:lower:]'
}

use_temp_tunnel() {
  # Explicit override wins.
  if [[ "${USE_TEMP_TUNNEL:-}" == "0" || "${SUPERVISE_MODE:-}" == "production" ]]; then
    return 1
  fi
  if [[ "${USE_TEMP_TUNNEL:-}" == "1" ]]; then
    return 0
  fi
  local env
  env="$(read_app_env)"
  [[ "$env" != "production" ]]
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

kill_cloudflared_strays() {
  local sig="${1:-TERM}"
  local pid cmd
  for pid in $(pgrep -f 'cloudflared tunnel' 2>/dev/null || true); do
    cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    if is_cloudflared_cmd "$cmd"; then
      log "kill stray cloudflared pid=$pid ($sig)"
      kill "-$sig" "$pid" 2>/dev/null || true
    fi
  done
}

kill_strays() {
  local sig="${1:-TERM}"
  local pid cmd
  for pid in $(pgrep -f 'python.*flypingavia|cloudflared tunnel' 2>/dev/null || true); do
    cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    if is_bot_cmd "$cmd"; then
      log "kill stray bot pid=$pid ($sig)"
      kill "-$sig" "$pid" 2>/dev/null || true
    fi
    if is_cloudflared_cmd "$cmd"; then
      log "kill stray cloudflared pid=$pid ($sig)"
      kill "-$sig" "$pid" 2>/dev/null || true
    fi
  done
}

tunnel_metrics_port() {
  # cloudflared --metrics 127.0.0.1:PORT
  awk '/metrics/ {for(i=1;i<=NF;i++) if($i ~ /127\.0\.0\.1:[0-9]+/) {split($i,a,":"); print a[2]; exit}}' \
    "$TUNNEL_LOG" 2>/dev/null || true
}

tunnel_ha_ok() {
  local port body ha
  port="$(tunnel_metrics_port)"
  [[ -n "$port" ]] || return 1
  body="$(curl -sf -m 3 "http://127.0.0.1:${port}/metrics" 2>/dev/null || true)"
  [[ -n "$body" ]] || return 1
  echo "$body" >"$METRICS_FILE"
  ha="$(echo "$body" | awk '/^cloudflared_tunnel_ha_connections / {print $2; exit}')"
  [[ -n "$ha" && "$ha" != "0" && "$ha" != "0.0" ]]
}

extract_tunnel_url() {
  grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | tail -n1 || true
}

start_bot() {
  stop_pid "$BOT_PID_FILE" "bot"
  log "запускаю python -m flypingavia"
  nohup python -m flypingavia >>"$BOT_LOG" 2>&1 &
  echo $! >"$BOT_PID_FILE"
  local _
  for _ in $(seq 1 40); do
    if local_health_ok; then
      log "bot health ok"
      return 0
    fi
    sleep 0.5
  done
  log "ERROR: bot health timeout"
  return 1
}

start_tunnel() {
  stop_pid "$TUNNEL_PID_FILE" "tunnel"
  kill_cloudflared_strays TERM
  sleep 0.5
  kill_cloudflared_strays KILL

  : >"$TUNNEL_LOG"
  log "запускаю cloudflared → http://${LOCAL_HOST}:${LOCAL_PORT}"
  nohup cloudflared tunnel --url "http://${LOCAL_HOST}:${LOCAL_PORT}" \
    --metrics "127.0.0.1:0" >>"$TUNNEL_LOG" 2>&1 &
  echo $! >"$TUNNEL_PID_FILE"

  local url="" _
  for _ in $(seq 1 "$TUNNEL_READY_TIMEOUT"); do
    if ! pid_alive "$(cat "$TUNNEL_PID_FILE" 2>/dev/null || true)"; then
      log "ERROR: cloudflared умер при старте"
      return 1
    fi
    url="$(extract_tunnel_url)"
    if [[ -n "$url" ]] && tunnel_ha_ok; then
      sleep "$DNS_WAIT_BEFORE_PROBE"
      echo "$url"
      return 0
    fi
    sleep 1
  done
  log "ERROR: tunnel ready timeout"
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

restart_stack_dev_tunnel() {
  log "полный рестарт стека (development temporary tunnel)"
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

restart_stack_production() {
  local url
  url="$(read_env_url)"
  if [[ -z "$url" ]]; then
    log "ERROR: APP_ENV=production требует WEBAPP_URL=https://… в $ENV_FILE"
    log "Temporary trycloudflare tunnel в production запрещён."
    return 1
  fi
  if [[ "$url" != https://* ]]; then
    log "ERROR: production WEBAPP_URL должен быть HTTPS: $url"
    return 1
  fi
  if [[ "$url" == *trycloudflare.com* ]]; then
    log "WARNING: trycloudflare.com — ephemeral; для production используйте named tunnel или свой домен"
  fi
  log "production mode: фиксированный WEBAPP_URL=$url (tunnel не перезаписывает)"
  if ! start_bot; then
    log "ERROR: бот не поднялся"
    return 1
  fi
  echo "$url" >"$URL_FILE"
  log "стек поднят (без temp tunnel): $url"
}

cleanup() {
  log "supervise останавливается (signal)"
  stop_pid "$TUNNEL_PID_FILE" "tunnel"
  stop_pid "$BOT_PID_FILE" "bot"
  exit 0
}

trap cleanup INT TERM

log "=== supervise start root=$ROOT app_env=$(read_app_env) ==="
kill_strays TERM
sleep 1
kill_strays KILL
sleep 1

if use_temp_tunnel; then
  restart_stack_dev_tunnel || true
else
  # Не трогаем чужие named tunnels; только гасим quick --url strays.
  kill_cloudflared_strays TERM || true
  restart_stack_production || true
fi

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

  if ! use_temp_tunnel; then
    # Production: только локальный health; публичный URL не переписываем.
    continue
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
    log "tunnel HA fail ($public_fails/$PUBLIC_FAILS_MAX)"
    if (( public_fails >= PUBLIC_FAILS_MAX )); then
      need_tunnel_restart=1
      public_fails=0
    fi
  else
    public_fails=0
  fi

  if (( need_tunnel_restart == 1 )); then
    if url="$(start_tunnel)"; then
      ensure_url_synced "$url"
    else
      log "ERROR: не удалось перезапустить tunnel"
    fi
  fi
done
