# Production recovery — FlyPing OPS-01

Версия продукта: **0.3.1**. Хост: Timeweb VPS (`/opt/flyping`).

## Архитектура

| Компонент | Где |
|---|---|
| Telegram bot + FastAPI API + Mini App static + checker + RL-03 | контейнер **`flyping-app`** (`flypingavia:0.3.1`, host network, `:8080`) |
| Marketing Next.js | контейнер **`flyping-site`** (`flyping-site:0.3.1`, host network, `:3000`) |
| TLS / reverse proxy | host **`nginx.service`** |
| SQLite | Docker volume **`flyping-data`** → `/app/data/flypingavia.db` |
| Compose project | `/opt/flyping/docker-compose.prod.yml` |

Bot / API / Mini App **не** разделены на отдельные контейнеры (осознанный SPOF `flyping-app`).

## Порядок автозапуска после reboot

1. `network-online.target`
2. `docker.service` (enabled)
3. `flyping.service` → `docker compose … up -d` (idempotent)
4. контейнеры с `restart: unless-stopped` + healthchecks
5. `nginx.service` (enabled, `Restart=on-failure`)
6. `flyping-watchdog.timer` → каждую минуту `health-watchdog.sh`

## Команды проверки

```bash
systemctl is-active docker flyping nginx
systemctl status flyping.service --no-pager
docker ps --format 'table {{.Names}}\t{{.Status}}'
docker inspect -f '{{.State.Health.Status}} mem={{.HostConfig.Memory}}' flyping-app flyping-site
curl -sf https://api.flyping.ru/api/ready
curl -sf -o /dev/null -w '%{http_code}\n' https://app.flyping.ru/
curl -sf -o /dev/null -w '%{http_code}\n' https://flyping.ru/
systemctl list-timers | grep flyping
journalctl -u flyping-watchdog.service -n 50 --no-pager
```

## Ручное восстановление

```bash
# Весь стек Compose
systemctl start flyping.service

# Только app / site
docker restart flyping-app
docker restart flyping-site

# Nginx
sudo systemctl restart nginx
sudo nginx -t
```

### App unhealthy

1. `docker logs --tail 200 flyping-app`
2. `curl -sf http://127.0.0.1:8080/api/ready`
3. `docker restart flyping-app` → дождаться `healthy` (start_period до 120s)
4. Если контейнера нет: `systemctl start flyping.service`

### Site unhealthy

1. `docker logs --tail 200 flyping-site`
2. `curl -sf http://127.0.0.1:3000/`
3. `docker restart flyping-site`
4. Проверить, что nginx проксирует на `:3000` (если не stub-режим)

### Nginx failed

1. `sudo nginx -t`
2. `sudo systemctl restart nginx`
3. `systemctl show nginx -p Restart -p NRestarts`

### После reboot

1. SSH / Timeweb console
2. `systemctl is-active docker flyping nginx`
3. `docker ps` — оба healthy
4. HTTP 200 на api / app / site
5. Проверить, что бот отвечает в Telegram (`/start`)

## Backup

- Timer: `flyping-backup.timer` → `flyping-backup.service` → `deploy/scripts/backup-db.sh`
- Файлы: `/var/backups/flyping/flypingavia-YYYYMMDDTHHMMSSZ.db`
- Копия через SQLite `backup()` API (консистентный снимок); fallback — `docker cp`
- **Не** восстанавливать DB на production без отдельного плана

Проверка integrity на **копии** (не на live DB):

```bash
LATEST=$(ls -1t /var/backups/flyping/flypingavia-*.db | head -1)
python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('PRAGMA integrity_check').fetchone()[0])" "$LATEST"
```

## Безопасный rollback лендинга

```bash
sudo /opt/flyping/deploy/scripts/rollback-landing.sh
```

Скрипт:

- восстанавливает stub в `/var/www/flyping-landing`;
- переключает nginx блок `flyping.ru` на stub;
- **не** делает `compose stop`;
- выполняет `compose up -d flyping-site` и ждёт healthcheck;
- проверяет HTTP 200 `https://flyping.ru`;
- **не** трогает volume `flyping-data` и `flyping-app`.

## Ограничения ресурсов (OPS-01 baseline ~4 GiB / 2 CPU)

| Сервис | mem_limit | cpus |
|---|---|---|
| flyping-app | 2500m (~65% RAM) | 1.6 |
| flyping-site | 900m (~23% RAM) | 1.0 |

Запас для Docker daemon, nginx, OS, SSH, backup. Swap на VPS может отсутствовать.

## Watchdog

- Script: `/opt/flyping/scripts/health-watchdog.sh`
- Timer: каждую **1 минуту** (`OnUnitActiveSec=1min`)
- Порог: **3** подряд неуспешные проверки
- Cooldown: **1 restart / 10 минут** на компонент
- State: `/run/flyping-watchdog/`
- Действия: `docker restart` app/site, `systemctl restart nginx`, `systemctl start flyping` если контейнеры отсутствуют
- Telegram-алерты **не** входят в OPS-01

## Docker live-restore

Включён в `/etc/docker/daemon.json` (`"live-restore": true`), если применено на хосте.  
Проверка: `docker info | grep -i 'Live Restore'`

## Graceful shutdown

В `docker-compose.prod.yml` для обоих сервисов: `init: true`, `stop_grace_period: 30s`  
(на Docker 29: `Config.StopTimeout=30`). При `docker stop` / compose stop процесс получает SIGTERM и до 30s на завершение, затем SIGKILL.

## Restart policy

Контейнеры: **`unless-stopped`**.  
Явный `docker kill` / `docker stop` на Docker 29 может **не** поднять контейнер (restart-manager останавливается) — используйте crash PID / `docker restart` / `systemctl start flyping`.
