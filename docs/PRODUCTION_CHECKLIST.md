# FlyPingAvia — production HTTPS checklist (WA-02)
#
# Код и шаблоны готовы; полный статус WA-02 = Done только после живого
# постоянного URL + BotFather. Этот файл — ручной ops checklist.

## A. Домен и TLS

- [ ] Купить/использовать домен (или named Cloudflare Tunnel hostname)
- [ ] DNS A/AAAA или CNAME → сервер / tunnel
- [ ] Reverse proxy: `deploy/caddy/Caddyfile.example` или `deploy/nginx/flyping.conf.example`
- [ ] HTTPS работает в браузере: `https://app.example.com/`

## B. Приложение

- [ ] `.env`: `APP_ENV=production`
- [ ] `.env`: `WEBAPP_URL=https://app.example.com` (без `/`, query, fragment; **не** `*.trycloudflare.com`)
- [ ] Quick tunnel / trycloudflare — только `APP_ENV=development`
- [ ] Named tunnel на **своём** hostname — допустим в production
- [ ] `.env`: `WEBAPP_DEV_USER_ID=0`
- [ ] `.env`: `TRAVELPAYOUTS_TOKEN=…` (иначе health `DEMO_PRICES_ENABLED`)
- [ ] `.env`: `DISPLAY_TIMEZONE=Europe/Moscow` (или ваша бизнес-TZ)
- [ ] `FORWARDED_ALLOW_IPS=127.0.0.1` (IP reverse proxy)
- [ ] SQLite volume / `data/` персистентен
- [ ] Локально: `curl -sf http://127.0.0.1:8080/api/health`
- [ ] Публично: `curl -sf https://app.example.com/api/ready` → `{"ready":true,…}`
- [ ] (RL-03) `.env`: `ADMIN_TELEGRAM_CHAT_ID=…` для служебных алертов (опционально; пусто = disabled)
- [ ] (RL-03) Startup log: `Admin health alerts: enabled|disabled`
- [ ] (RL-03) Миграция/таблицы: `system_health_incidents`, `system_runtime_state`

## C. Supervise / tunnel

- [ ] Production: **не** использовать `cloudflared tunnel --url` (trycloudflare)
- [ ] `scripts/supervise.sh` при `APP_ENV=production` не переписывает `WEBAPP_URL`
- [ ] Невалидный production startup (`WEBAPP_URL` пуст / HTTP / trycloudflare) → supervise **exit ≠ 0**
- [ ] Named tunnel (опционально): `deploy/cloudflared/config.yml.example`

## D. BotFather (вручную)

- [ ] `/setmenubutton` → бот → текст кнопки → `https://app.example.com`
- [ ] при необходимости `/setdomain` → тот же hostname
- [ ] Открыть Mini App из Telegram (не HTTP, не localhost)

## E. Безопасность

- [ ] `.env` и tunnel credentials не в git
- [ ] Health/ready не содержат tokens
- [ ] CORS не нужен (same-origin static+API)
- [ ] Не доверять Host header для canonical URL
