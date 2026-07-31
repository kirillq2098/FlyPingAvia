#!/usr/bin/env bash
# Daily SQLite backup for FlyPing (IN-04). No secrets in logs.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/flyping}"
COMPOSE_FILE="${COMPOSE_FILE:-/opt/flyping/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-/opt/flyping/.env}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BACKUP_DIR}/flypingavia-${STAMP}.db"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

if ! docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps --status running -q flyping >/dev/null 2>&1; then
  # fallback: container name
  if ! docker ps --filter name=flyping-app --filter status=running -q | grep -q .; then
    echo "backup-db: container not running" >&2
    exit 1
  fi
fi

# Copy SQLite file from volume via container
docker cp flyping-app:/app/data/flypingavia.db "$OUT"
chmod 600 "$OUT"
SIZE="$(stat -c '%s' "$OUT")"
if [[ "$SIZE" -lt 1 ]]; then
  echo "backup-db: empty file" >&2
  exit 1
fi

find "$BACKUP_DIR" -type f -name 'flypingavia-*.db' -mtime "+${RETENTION_DAYS}" -delete || true
echo "backup-db: OK bytes=${SIZE} file=${OUT}"
