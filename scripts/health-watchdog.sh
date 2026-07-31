#!/usr/bin/env bash
# OPS-01 health watchdog — periodic checks + limited auto-restart.
# Invoked by systemd timer (oneshot). No Telegram alerts here.
set -euo pipefail

STATE_DIR="${STATE_DIR:-/run/flyping-watchdog}"
COMPOSE_FILE="${COMPOSE_FILE:-/opt/flyping/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-/opt/flyping/.env}"
FAIL_THRESHOLD="${FAIL_THRESHOLD:-3}"
RESTART_COOLDOWN_SEC="${RESTART_COOLDOWN_SEC:-600}"

API_URL="${API_URL:-https://api.flyping.ru/api/ready}"
SITE_URL="${SITE_URL:-https://flyping.ru/}"
APP_URL="${APP_URL:-https://app.flyping.ru/}"

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"

log() {
  # journald picks up stdout from systemd oneshot
  echo "flyping-watchdog: $*"
}

now_epoch() { date +%s; }

get_fail() {
  local key="$1"
  local f="$STATE_DIR/${key}.fails"
  if [[ -f "$f" ]]; then cat "$f"; else echo 0; fi
}

set_fail() {
  local key="$1"
  local n="$2"
  echo "$n" >"$STATE_DIR/${key}.fails"
}

reset_fail() { set_fail "$1" 0; }

last_restart_age() {
  local key="$1"
  local f="$STATE_DIR/${key}.last_restart"
  if [[ ! -f "$f" ]]; then
    echo 999999
    return
  fi
  local ts
  ts=$(cat "$f")
  echo $(( $(now_epoch) - ts ))
}

can_restart() {
  local key="$1"
  local age
  age=$(last_restart_age "$key")
  [[ "$age" -ge "$RESTART_COOLDOWN_SEC" ]]
}

http_ok() {
  local url="$1"
  local code
  code=$(curl -sf -o /dev/null -w '%{http_code}' --max-time 8 "$url" || echo 000)
  [[ "$code" == "200" ]]
}

container_running() {
  docker ps --filter "name=^/${1}$" --filter status=running -q | grep -q .
}

container_health() {
  # healthy | starting | unhealthy | none | missing
  local name="$1"
  if ! docker inspect "$name" >/dev/null 2>&1; then
    echo missing
    return
  fi
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name" 2>/dev/null || echo missing
}

nginx_active() {
  systemctl is-active --quiet nginx
}

do_restart_container() {
  local name="$1"
  local key="$2"
  if ! can_restart "$key"; then
    log "skip restart $name (cooldown ${RESTART_COOLDOWN_SEC}s)"
    return 0
  fi
  log "restarting container $name"
  if ! container_running "$name" && ! docker inspect "$name" >/dev/null 2>&1; then
    log "container $name missing — starting flyping.service"
    systemctl start flyping.service || true
  else
    docker restart "$name" || systemctl start flyping.service || true
  fi
  echo "$(now_epoch)" >"$STATE_DIR/${key}.last_restart"
  reset_fail "$key"
}

do_restart_nginx() {
  local key=nginx
  if ! can_restart "$key"; then
    log "skip restart nginx (cooldown)"
    return 0
  fi
  log "restarting nginx"
  systemctl restart nginx || true
  echo "$(now_epoch)" >"$STATE_DIR/${key}.last_restart"
  reset_fail "$key"
}

check_component() {
  local key="$1"
  local ok="$2" # 0/1
  if [[ "$ok" == "1" ]]; then
    reset_fail "$key"
    return 0
  fi
  local n
  n=$(get_fail "$key")
  n=$((n + 1))
  set_fail "$key" "$n"
  log "fail $key count=$n/${FAIL_THRESHOLD}"
  if [[ "$n" -ge "$FAIL_THRESHOLD" ]]; then
    return 1
  fi
  return 0
}

# --- checks ---
app_h=$(container_health flyping-app)
site_h=$(container_health flyping-site)
app_run=0
site_run=0
container_running flyping-app && app_run=1 || true
container_running flyping-site && site_run=1 || true

api_ok=0
site_http_ok=0
app_http_ok=0
http_ok "$API_URL" && api_ok=1 || true
http_ok "$SITE_URL" && site_http_ok=1 || true
http_ok "$APP_URL" && app_http_ok=1 || true

ngx_ok=0
nginx_active && ngx_ok=1 || true

log "status app_health=$app_h app_run=$app_run api_http=$api_ok site_health=$site_h site_run=$site_run site_http=$site_http_ok app_http=$app_http_ok nginx=$ngx_ok"

# Missing project entirely
if [[ "$app_run" != "1" && "$app_h" == "missing" && "$site_run" != "1" && "$site_h" == "missing" ]]; then
  if check_component project 0; then
    :
  else
    if can_restart project; then
      log "starting flyping.service (containers missing)"
      systemctl start flyping.service || true
      echo "$(now_epoch)" >"$STATE_DIR/project.last_restart"
      reset_fail project
    fi
  fi
else
  reset_fail project
fi

# flyping-app: unhealthy or not running or API down
app_component_ok=1
if [[ "$app_run" != "1" || "$app_h" == "unhealthy" || "$app_h" == "missing" || "$api_ok" != "1" ]]; then
  # tolerate "starting" without counting as hard fail unless HTTP also fails repeatedly
  if [[ "$app_h" == "starting" && "$app_run" == "1" ]]; then
    app_component_ok=1
  else
    app_component_ok=0
  fi
fi
if check_component app "$app_component_ok"; then
  :
else
  do_restart_container flyping-app app
fi

# flyping-site
site_component_ok=1
if [[ "$site_run" != "1" || "$site_h" == "unhealthy" || "$site_h" == "missing" ]]; then
  if [[ "$site_h" == "starting" && "$site_run" == "1" ]]; then
    site_component_ok=1
  else
    site_component_ok=0
  fi
fi
# site HTTP via public URL may be stub or next — still require 200
if [[ "$site_http_ok" != "1" ]]; then
  site_component_ok=0
fi
if check_component site "$site_component_ok"; then
  :
else
  do_restart_container flyping-site site
fi

# nginx
if check_component nginx "$ngx_ok"; then
  :
else
  do_restart_nginx
fi

# Mini App public HTTP — if app container ok but edge fails, nudge nginx once threshold hit
edge_ok=1
if [[ "$app_http_ok" != "1" || "$api_ok" != "1" ]]; then
  edge_ok=0
fi
if check_component edge "$edge_ok"; then
  :
else
  # Prefer nginx reload/restart if containers look fine
  if [[ "$app_run" == "1" && "$app_h" == "healthy" ]]; then
    do_restart_nginx
  else
    do_restart_container flyping-app app
  fi
fi

exit 0
