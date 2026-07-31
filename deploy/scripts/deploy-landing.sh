#!/usr/bin/env bash
# Publish marketing Next.js site to flyping.ru / www (keeps app + api untouched).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/flyping}"
STUB_ROOT="${STUB_ROOT:-/var/www/flyping-landing}"
NGINX_SRC="${NGINX_SRC:-$ROOT/deploy/nginx/flyping.conf}"
NGINX_DST="${NGINX_DST:-/etc/nginx/sites-available/flyping}"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$BACKUP_ROOT/landing-stub-$stamp"

echo "deploy-landing: backup stub → $backup_dir"
mkdir -p "$BACKUP_ROOT"
if [[ -d "$STUB_ROOT" ]]; then
  cp -a "$STUB_ROOT" "$backup_dir"
else
  mkdir -p "$backup_dir"
  echo "(no existing stub)" >"$backup_dir/README.txt"
fi

echo "deploy-landing: build + start flyping-site"
docker compose -f "$COMPOSE_FILE" up -d --build flyping-site

echo "deploy-landing: wait for site on :3000"
for i in $(seq 1 40); do
  if curl -sf --max-time 3 http://127.0.0.1:3000/ >/dev/null; then
    echo "deploy-landing: site ready"
    break
  fi
  if [[ "$i" -eq 40 ]]; then
    echo "deploy-landing: site failed readiness" >&2
    docker compose -f "$COMPOSE_FILE" logs --tail 80 flyping-site >&2 || true
    exit 1
  fi
  sleep 3
done

echo "deploy-landing: install nginx config"
cp -f "$NGINX_SRC" "$NGINX_DST"
ln -sfn "$NGINX_DST" /etc/nginx/sites-enabled/flyping
nginx -t
systemctl reload nginx

echo "deploy-landing: done (backup kept at $backup_dir)"
curl -sI https://flyping.ru | head -8 || true
