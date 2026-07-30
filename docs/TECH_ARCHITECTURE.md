# Tech Architecture — FlyPingAvia

Связанные документы: [Vision](PRODUCT_VISION.md) · [Roadmap](MASTER_ROADMAP.md) · [Decisions](DECISIONS.md) · [Changelog](CHANGELOG.md)

Описание **текущей** архитектуры по коду. Планы масштабирования — только в TODO.

## Обзор

```text
Telegram users
    │  polling (aiogram)
    ▼
┌─────────────────────────────────────────────┐
│  flypingavia.main                           │
│  ├─ Bot + Dispatcher (handlers)             │
│  ├─ APScheduler → PriceChecker.run_once     │
│  └─ uvicorn → FastAPI Mini App + /api/*     │
└───────────────┬─────────────────────────────┘
                │
       ┌────────┴────────┐
       ▼                 ▼
  SQLite (users,     Travelpayouts
   watches)          Data API / optional
                     Flight Search API
                     + Aviasales affiliate URLs
```

Точка входа: `python -m flypingavia` → `flypingavia.main:run`.

## Стек (факт)

| Слой | Технология |
|------|------------|
| Язык | Python ≥3.11 (Docker: 3.12-slim) |
| Бот | aiogram 3 |
| HTTP API / Mini App | FastAPI + uvicorn (`version` из `flypingavia.version`) |
| Планировщик | APScheduler (AsyncIO) |
| ORM / БД | SQLAlchemy 2 + aiosqlite |
| HTTP-клиент | httpx |
| Конфиг | pydantic-settings + `.env` |
| Статика Mini App | `flypingavia/web/static/*` (без сборщика) |

Зависимости: `requirements.txt` / `pyproject.toml`.

## Модули

| Путь | Назначение |
|------|------------|
| `flypingavia/main.py` | Старт бота, scheduler, uvicorn (+ proxy headers); сброс MenuButton в commands |
| `flypingavia/config.py` | Settings: `APP_ENV`, WEBAPP_*, readiness |
| `flypingavia/webapp_url.py` | Нормализация/валидация canonical WEBAPP_URL |
| `flypingavia/bot/handlers.py` | Команды, FSM, колбэки |
| `flypingavia/bot/keyboards.py` | Reply/Inline клавиатуры (WebApp только публичный HTTPS) |
| `flypingavia/bot/formatters.py` | Тексты карточек/алертов |
| `flypingavia/api/app.py` | FastAPI routes + static; `/api/health`, `/api/ready` |
| `flypingavia/api/telegram_auth.py` | Проверка WebApp `initData` |
| `flypingavia/db/models.py` | `User`, `Watch` |
| `flypingavia/db/repository.py` | CRUD подписок |
| `flypingavia/db/session.py` | Engine, `init_db`, SQLite ALTER для новых колонок |
| `flypingavia/services/prices.py` | Demo / Travelpayouts quotes, band, affiliate URL |
| `flypingavia/services/flight_search.py` | Affiliate Flight Search start/results |
| `flypingavia/services/checker.py` | Фоновые проверки и алерты |
| `flypingavia/services/locations.py` | Справочник городов/аэропортов |
| `scripts/supervise.sh` | Watchdog: production = фиксированный WEBAPP_URL; development = optional quick tunnel |
| `deploy/` | Nginx/Caddy/cloudflared/compose examples |

## HTTP API Mini App

| Метод | Путь | Auth |
|-------|------|------|
| GET | `/` | нет (index.html) |
| GET | `/assets/*` | нет |
| GET | `/api/health` | нет (liveness + readiness flags) |
| GET | `/api/ready` | нет (200/503 относительно `APP_ENV`) |
| GET | `/api/me` | да |
| GET | `/api/resolve?q=` | да |
| GET | `/api/quote` | да |
| GET | `/api/watches` | да |
| POST | `/api/watches` | да |
| DELETE | `/api/watches/{id}` | да |

Auth (WA-03):

1. Предпочтительный заголовок: `Authorization: tma <initData>` (legacy `X-Telegram-Init-Data` ещё принимается backend).
2. Проверка: официальный HMAC (`secret = HMAC_SHA256(key="WebAppData", msg=bot_token)`), `hmac.compare_digest`, `auth_date` ≤ `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS` (default **3600**), future skew ≤ 30 с.
3. Telegram user id берётся **только** из проверенного `user` JSON; frontend id / query / body не доверенные.
4. Production: без валидного initData → `401` (`MISSING_INIT_DATA` / `INVALID_HASH` / …). `WEBAPP_DEV_USER_ID` обязан быть `0`.
5. Development/test: без initData допускается `WEBAPP_DEV_USER_ID > 0`; плохой initData **не** падает в dev-fallback.
6. Изоляция: `get_or_create_user(telegram_id)` → `list_watches` / `deactivate_watch` только для своего `user_id`; чужой watch → `404`.
7. Health публичный; безопасные поля: `telegram_webapp_auth`, опционально `telegram_bot_username` / `telegram_bot_link` (без token / dev user id).

Подробности: [SECURITY.md](SECURITY.md).

## Модель данных

**users:** `id`, `telegram_id` (unique), `username`, `created_at`

**watches:** маршрут (`origin`/`destination` + names + `*_search` CSV кодов), `max_price`, `depart_date`, `return_date`, `adults`/`children`/`infants`, `currency`, `flexibility_days`, `last_price`, `last_*_airport`, `last_checked_at` (UTC, момент завершённой проверки), `last_alert_price`, `is_active`, `created_at`

**Отображение времени:** `DISPLAY_TIMEZONE` (default `Europe/Moscow`) — только UI; в БД всегда UTC.

Удаление подписки — soft (`is_active=False`).

## Источники цен

1. **DemoPriceProvider** — если нет `TRAVELPAYOUTS_TOKEN`  
2. **TravelpayoutsPriceProvider** — month-matrix / calendar / latest; round-trip ≈ сумма one-way  
3. **Flight Search** (опционально) — если `LIVE_SEARCH_MODE` ∈ {multi, always, …} и есть token + search marker; UI пассажиров при этом скрыт

`v1/prices/cheap` в коде объявлен, для датированных one-way **не используется** (см. [DECISIONS](DECISIONS.md)).

## Фоновые задачи

- Job id `price_check`, interval = `poll_interval_seconds` (минимум 30 сек, если из минут).  
- `PriceChecker.run_once`: все активные watches → quote → update last_* → алерт если цена ≤ порога.

## Деплой и эксплуатация

Целевая схема production (WA-02):

```text
Telegram → https://app.example.com → reverse proxy → 127.0.0.1:8080 (FastAPI+static)
```

- `APP_ENV=production` требует canonical HTTPS `WEBAPP_URL` (без path/query); `WEBAPP_DEV_USER_ID=0`
- CORS не нужен: UI и API на одном origin
- Proxy: `FORWARDED_ALLOW_IPS=127.0.0.1` (не `*`); canonical URL **не** берётся из Host
- Примеры: `deploy/nginx/`, `deploy/caddy/`, `deploy/cloudflared/`, `deploy/docker-compose.production.example.yml`
- Checklist: [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)
- `scripts/supervise.sh`: в production **не** запускает trycloudflare и **не** переписывает `WEBAPP_URL`; temporary tunnel — только development
- Docker: non-root `appuser`, HEALTHCHECK на `/api/health`, secrets только через env
- Логи watchdog: `/tmp/flypingavia/`

## Тесты

- `pytest -q` — unit/integration (в т.ч. WA-03 initData/HMAC/isolation, WA-02 URL/health/ready, TR-04, CS/NT)  
- Auth Mini App: `tests/test_wa03_telegram_auth.py`, `tests/test_webapp_auth.py`

## TODO — архитектура на рост

- [ ] Когда переходим с SQLite на Postgres (при каком N users / watches)?
- [ ] Нужен ли отдельный worker процесса проверки цен от polling бота?
- [ ] Как хранить и ротировать секреты вне `.env` на одном сервере?
- [x] Named Cloudflare Tunnel / свой домен — шаблоны в `deploy/` (ops остаётся)
- [ ] Нужна ли очередь (Redis и т.п.) или хватит APScheduler до v1.0?