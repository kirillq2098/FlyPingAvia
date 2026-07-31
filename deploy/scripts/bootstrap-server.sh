#!/usr/bin/env bash
# Bootstrap Ubuntu 24.04 Timeweb VPS for FlyPing (IN-04).
# Run as root on the server. Idempotent where practical.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get upgrade -y
apt-get install -y \
  ca-certificates curl gnupg git ufw nginx \
  python3 python3-venv \
  certbot python3-certbot-nginx \
  jq openssl dnsutils

# Docker Engine (official)
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

systemctl enable --now docker

# Directories
mkdir -p /opt/flyping
mkdir -p /var/www/certbot
mkdir -p /var/www/flyping-landing
mkdir -p /var/backups/flyping
chmod 700 /var/backups/flyping

# Firewall: SSH first, then HTTP/HTTPS. No 5432 / 8080.
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose

echo "bootstrap-server: OK"
