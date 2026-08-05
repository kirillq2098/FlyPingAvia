# Deploy FlyPingAvia on Timeweb Cloud VPS (IN-04)

Связанные: [PRODUCTION_CHECKLIST](PRODUCTION_CHECKLIST.md) · [HEALTH_MONITORING](HEALTH_MONITORING.md) · [SECURITY](SECURITY.md)

## Целевая схема (v0.3.1)

```text
Internet → Nginx (TLS) → 127.0.0.1:8080 → Docker container flyping-app
                                              ├─ Telegram bot (polling)
                                              ├─ FastAPI Mini App + /api/*
                                              ├─ APScheduler price checker
                                              └─ RL-03 HealthMonitor
                         SQLite volume: flyping-data
```

PostgreSQL в коде **не** поддержан — production использует SQLite.

## Сервер

| Параметр | Значение |
|----------|----------|
| Provider | Timeweb Cloud |
| Host | `5.129.195.36` |
| OS | Ubuntu 24.04 LTS |
| Install dir | `/opt/flyping` |
| Domains | `flyping.ru`, `app.flyping.ru`, `api.flyping.ru` |
| Mini App | `https://app.flyping.ru` |

## Production branch

Согласованная ветка: `cursor/gr-02-blogger-kit-3bd9` (включает RL-03 / GR-02).  
На сервере фиксируйте SHA из `git rev-parse HEAD` после deploy.

## DNS

```text
A  @    5.129.195.36
A  www  5.129.195.36
A  app  5.129.195.36
A  api  5.129.195.36
```

## Bootstrap

```bash
ssh root@5.129.195.36
# скопировать репозиторий в /opt/flyping, затем:
bash /opt/flyping/deploy/scripts/bootstrap-server.sh
```

Ставит Docker, Nginx, Certbot, UFW (22/80/443). Порт 8080 и 5432 наружу **не** открываются.

## Environment

```bash
cp /opt/flyping/.env.production.example /opt/flyping/.env
# заполнить секреты локально на сервере (не в чат)
chmod 600 /opt/flyping/.env
```

Обязательно:

- `BOT_TOKEN`
- `TELEGRAM_BOT_USERNAME` (без `@`)
- `WATCH_SHARE_CALLBACK_SECRET` (`openssl rand -hex 32`)
- `WEBAPP_URL=https://app.flyping.ru`
- `APP_ENV=production`
- `WEBAPP_DEV_USER_ID=0`
- `TRAVELPAYOUTS_TOKEN` (иначе ready → DEMO)

`.env` в Git **не** коммитить.

## Сеть и Telegram

На части VPS Timeweb `api.telegram.org` отвечает только по **IPv6**; IPv4 может таймаутиться.
В `docker-compose.prod.yml` сервис `flyping` использует `network_mode: host`, чтобы наследовать IPv6 хоста.
Приложение слушает `127.0.0.1:8080` (не публикует 8080 наружу через UFW).

## Deploy

```bash
cd /opt/flyping
./deploy/scripts/deploy.sh
```

`init_db()` при старте создаёт/догоняет схему SQLite.

## Nginx + TLS

1. HTTP bootstrap: `deploy/nginx/flyping.http-bootstrap.conf`  
2. Certbot webroot для `flyping.ru www.flyping.ru app.flyping.ru api.flyping.ru`  
3. Установить `deploy/nginx/flyping.conf`  
4. `nginx -t && systemctl reload nginx`  
5. `certbot renew --dry-run`

Landing: `/var/www/flyping-landing` из `deploy/landing/` (deployment stub).

Фронтенды в репозитории (v0.3.1):

| Host | Каталог | Что это |
|------|---------|---------|
| `flyping.ru` / `www` | `website/` (Next.js → container `:3000`) | Marketing site (airport redesign) |
| `app.flyping.ru` | `flypingavia/web/static/` | Telegram Mini App |
| stub backup | `/var/backups/flyping/landing-stub-*` | Rollback via `deploy/scripts/rollback-landing.sh` |

Startup menu button: стабильный `WEBAPP_URL` → `MenuButtonWebApp` («FlyPing»); temporary tunnel → `MenuButtonCommands` (TG-05).

## Polling

Один экземпляр бота. Перед стартом удалить webhook (без печати токена):

```bash
# на сервере, токен читается из .env внутри скрипта
set -a; source /opt/flyping/.env; set +a
curl -sS "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook?drop_pending_updates=true" >/dev/null
unset BOT_TOKEN
```

Не запускайте локальный бот с тем же токеном параллельно.

## Health

```bash
./deploy/scripts/health-check.sh
curl -sf https://app.flyping.ru/api/ready
curl -sf https://api.flyping.ru/api/health
```

## Backup (SQLite)

```bash
./deploy/scripts/backup-db.sh
# systemd timer daily → /var/backups/flyping (retention 7d)
```

Restore (документация, не выполнять без необходимости):

```bash
docker compose -f docker-compose.prod.yml --env-file .env stop flyping
docker cp /var/backups/flyping/flypingavia-TIMESTAMP.db flyping-app:/app/data/flypingavia.db
docker compose -f docker-compose.prod.yml --env-file .env start flyping
```

## BotFather (вручную)

1. `@BotFather` → ваш бот  
2. Menu Button → Web App URL: `https://app.flyping.ru`  
3. `/setdomain` → `app.flyping.ru` (если требуется)  
4. Commands: start, help, add, list, …

## Private GitHub

Deploy key (read-only) на сервере в `/root/.ssh/flyping_deploy`.  
Не кладите PAT в remote URL.

## Файлы

- `docker-compose.prod.yml`
- `deploy/nginx/flyping.conf`
- `deploy/scripts/bootstrap-server.sh`
- `deploy/scripts/deploy.sh`
- `deploy/scripts/health-check.sh`
- `deploy/scripts/backup-db.sh`
- `.env.production.example`
