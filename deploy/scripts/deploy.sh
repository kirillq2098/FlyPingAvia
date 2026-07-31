#!/usr/bin/env bash
# Deploy / update FlyPing on this host (IN-04).
# Expected cwd: /opt/flyping with docker-compose.prod.yml and .env
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"
BRANCH="${DEPLOY_BRANCH:-cursor/in-04-production-deployment-3bd9}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Missing $COMPOSE_FILE" >&2
  exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE (chmod 600). Fill from .env.production.example" >&2
  exit 1
fi
if [[ "$(stat -c '%a' "$ENV_FILE" 2>/dev/null || echo 0)" != "600" ]]; then
  chmod 600 "$ENV_FILE"
fi

echo "deploy: validating compose (secrets not printed)"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" config >/dev/null

if [[ -d .git ]]; then
  echo "deploy: git fetch / ff-only pull ($BRANCH)"
  git fetch origin "$BRANCH"
  current="$(git rev-parse --abbrev-ref HEAD)"
  if [[ "$current" != "$BRANCH" ]]; then
    git checkout "$BRANCH"
  fi
  git merge --ff-only "origin/$BRANCH"
fi

echo "deploy: SHA=$(git rev-parse HEAD 2>/dev/null || echo unknown)"

echo "deploy: build + up"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build

echo "deploy: wait for healthy"
for i in $(seq 1 40); do
  if curl -sf --max-time 3 http://127.0.0.1:8080/api/ready >/dev/null; then
    echo "deploy: ready OK"
    curl -sf http://127.0.0.1:8080/api/health | head -c 400 || true
    echo
    exit 0
  fi
  sleep 3
done

echo "deploy: readiness failed" >&2
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps >&2 || true
exit 1
