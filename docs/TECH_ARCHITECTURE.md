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
| HTTP API / Mini App | FastAPI + uvicorn |
| Планировщик | APScheduler (AsyncIO) |
| ORM / БД | SQLAlchemy 2 + aiosqlite |
| HTTP-клиент | httpx |
| Конфиг | pydantic-settings + `.env` |
| Статика Mini App | `flypingavia/web/static/*` (без сборщика) |

Зависимости: `requirements.txt` / `pyproject.toml`.

## Модули

| Путь | Назначение |
|------|------------|
| `flypingavia/main.py` | Старт бота, scheduler, uvicorn; сброс MenuButton в commands |
| `flypingavia/config.py` | Settings, demo/live флаги, интервал polling |
| `flypingavia/bot/handlers.py` | Команды, FSM, колбэки |
| `flypingavia/bot/keyboards.py` | Reply/Inline клавиатуры |
| `flypingavia/bot/formatters.py` | Тексты карточек/алертов |
| `flypingavia/api/app.py` | FastAPI routes + раздача static |
| `flypingavia/api/telegram_auth.py` | Проверка WebApp `initData` |
| `flypingavia/db/models.py` | `User`, `Watch` |
| `flypingavia/db/repository.py` | CRUD подписок |
| `flypingavia/db/session.py` | Engine, `init_db`, SQLite ALTER для новых колонок |
| `flypingavia/services/prices.py` | Demo / Travelpayouts quotes, band, affiliate URL |
| `flypingavia/services/flight_search.py` | Affiliate Flight Search start/results |
| `flypingavia/services/checker.py` | Фоновые проверки и алерты |
| `flypingavia/services/locations.py` | Справочник городов/аэропортов |
| `scripts/supervise.sh` | Watchdog бота + cloudflared |

## HTTP API Mini App

| Метод | Путь | Auth |
|-------|------|------|
| GET | `/` | нет (index.html) |
| GET | `/assets/*` | нет |
| GET | `/api/health` | нет |
| GET | `/api/me` | да |
| GET | `/api/resolve?q=` | да |
| GET | `/api/quote` | да |
| GET | `/api/watches` | да |
| POST | `/api/watches` | да |
| DELETE | `/api/watches/{id}` | да |

Auth: заголовок `X-Telegram-Init-Data` или `Authorization: tma <initData>`; иначе `WEBAPP_DEV_USER_ID` для локальной отладки; иначе 401.  
Срок `initData`: `max_age_seconds=86400`.

## Модель данных

**users:** `id`, `telegram_id` (unique), `username`, `created_at`

**watches:** маршрут (`origin`/`destination` + names + `*_search` CSV кодов), `max_price`, `depart_date`, `return_date`, `adults`/`children`/`infants`, `currency`, `last_price`, `last_*_airport`, `last_checked_at`, `last_alert_price`, `is_active`, `created_at`

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

- Локально / VPS: `python -m flypingavia`  
- Docker: `Dockerfile`, volume на `./data`, `--env-file .env`  
- Mini App требует публичный HTTPS → `WEBAPP_URL`  
- `scripts/supervise.sh`: рестарт бота и cloudflared; при новом trycloudflare URL пишет `WEBAPP_URL` в `.env`  
- Логи watchdog: `/tmp/flypingavia/`

## Тесты

- `tests/test_core.py` — репозиторий, demo prices, affiliate URL, settings, formatters, resolve (сеть), live quote fake  
- `tests/test_webapp_auth.py` — HMAC initData  

Не покрыто автотестами: handlers/FSM, checker алерты, FastAPI integration, enforcement лимита.

## TODO — архитектура на рост

- [ ] Когда переходим с SQLite на Postgres (при каком N users / watches)?
- [ ] Нужен ли отдельный worker процесса проверки цен от polling бота?
- [ ] Как хранить и ротировать секреты вне `.env` на одном сервере?
- [ ] Нужен ли named Cloudflare Tunnel / свой домен вместо quick tunnel?
- [ ] Нужна ли очередь (Redis и т.п.) или хватит APScheduler до v1.0?
