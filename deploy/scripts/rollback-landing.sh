#!/usr/bin/env bash
# Rollback flyping.ru / www to the stub backup without touching SSL or Mini App/API.
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/flyping}"
STUB_ROOT="${STUB_ROOT:-/var/www/flyping-landing}"
COMPOSE_FILE="${COMPOSE_FILE:-/opt/flyping/docker-compose.prod.yml}"

latest="$(ls -1dt "$BACKUP_ROOT"/landing-stub-* 2>/dev/null | head -1 || true)"
if [[ -z "$latest" ]]; then
  echo "No stub backup found under $BACKUP_ROOT/landing-stub-*" >&2
  exit 1
fi

echo "rollback: restoring stub from $latest"
mkdir -p "$STUB_ROOT"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "$latest/" "$STUB_ROOT/"
else
  find "$STUB_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  cp -a "$latest"/. "$STUB_ROOT"/
fi

python3 - <<'PY'
from pathlib import Path

path = Path("/etc/nginx/sites-available/flyping")
text = path.read_text()

# Remove optional marketing upstream so stub-only config is valid.
marker = "upstream flyping_site"
if marker in text:
    u0 = text.find(marker)
    brace = text.find("{", u0)
    depth = 0
    i = brace
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                # drop trailing newline after block
                end = i + 1
                while end < len(text) and text[end] in "\r\n":
                    end += 1
                text = text[:u0] + text[end:]
                break
        i += 1

start = text.find("# --- Landing: flyping.ru ---")
if start < 0:
    start = text.find("# --- Marketing site: flyping.ru")
end = text.find("# --- Mini App + same-origin API: app.flyping.ru ---")
if start < 0 or end < 0:
    raise SystemExit("nginx landing markers not found")

block = """# --- Landing: flyping.ru ---

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name flyping.ru www.flyping.ru;

    ssl_certificate     /etc/letsencrypt/live/flyping.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/flyping.ru/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    root /var/www/flyping-landing;
    index index.html;

    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header X-Frame-Options DENY always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    location ~ /\\.(git|env|ht) {
        deny all;
        return 404;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}

"""
path.write_text(text[:start] + block + text[end:])
print("nginx landing block restored to static stub")
PY

nginx -t
systemctl reload nginx

if [[ -f "$COMPOSE_FILE" ]]; then
  docker compose -f "$COMPOSE_FILE" stop flyping-site 2>/dev/null || true
fi

echo "rollback: stub live on flyping.ru / www (SSL + app/api unchanged)"
curl -sI https://flyping.ru | head -5 || true
