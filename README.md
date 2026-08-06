# FlyPingAvia

Telegram-бот для мониторинга цен на авиабилеты.

Пользователь задаёт маршрут и порог цены — бот следит за предложениями и присылает алерт, когда билет стал дешевле. В алертах — партнёрская ссылка (CPA).

## Документация

Точка входа: **[docs/README.md](docs/README.md)**

| Документ | Содержание |
|----------|------------|
| [Product Vision](docs/PRODUCT_VISION.md) | Зачем продукт и что уже умеет |
| [Strategy](docs/FLYPING_STRATEGY.md) | USP, рост 100→100k, non-goals |
| [Feature Backlog](docs/FEATURE_BACKLOG.md) | Реестр функций и приоритеты |
| [User Journey](docs/USER_JOURNEY.md) | Путь пользователя и точки отказа |
| [Master Roadmap](docs/MASTER_ROADMAP.md) | Этапы развития и открытые вопросы |
| [Competitive Analysis](docs/COMPETITIVE_ANALYSIS.md) | Конкуренты и opportunities |
| [Tech Architecture](docs/TECH_ARCHITECTURE.md) | Стек, модули, API, данные |
| [Monetization](docs/MONETIZATION.md) | CPA в коде и стратегия дальше |
| [Marketing](docs/MARKETING.md) | Каналы и ограничения |
| [Decisions](docs/DECISIONS.md) | Зафиксированные решения |
| [Changelog](docs/CHANGELOG.md) | История изменений |
| [Copy Guide](docs/COPY_GUIDE.md) | Позиционирование «сторож цены», glossary |
| [Blogger Kit](docs/BLOGGER_KIT.md) | GR-02: тексты и ссылки для каналов/блогеров |
| [Closed Beta Playbook](docs/CLOSED_BETA_PLAYBOOK.md) | Запуск Closed Beta: инвайт, FAQ, опрос |
| [Beta Go-Live Checklist](docs/BETA_GO_LIVE_CHECKLIST.md) | Операции: deploy, migration 008, `BETA_ENABLED` |
| [Attribution](docs/ATTRIBUTION.md) | Deep-link `?start=`, first/last touch |
| [KPI](docs/KPI.md) | Метрики по этапам |

## Текущая версия: 0.3.1

Current application version: **0.3.1**

Проверка без запуска бота:

```bash
python -m flypingavia --version
# или: python -m flypingavia -V
```

Уже есть:

- Telegram Mini App с безопасной авторизацией через signed `initData` (WA-03)
- позиционирование: **сторож цены** на поездку, не каталог рейсов (TG-02)
- команды и кнопки меню: FlyPing / создать подписку / подписки / проверить / помощь
- города словами + поиск по всем аэропортам (самый дешёвый)
- вилка цен: дёшево / обычно / дорого + кнопки выбора порога
- гибкость дат ±1/±3/±7 (CS-07 MVP)
- SQLite-хранилище подписок
- фоновая проверка цен (APScheduler) + время последней проверки (TR-04)
- цены через Travelpayouts API или **demo-режим** без токена
- партнёрские ссылки Aviasales с `marker`
- живой поиск за взрослых/детей (Flight Search API, если Travelpayouts выдал доступ)
- production HTTPS config / readiness (WA-02 code; живой домен — ops)

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# впишите BOT_TOKEN от @BotFather
# опционально: TRAVELPAYOUTS_TOKEN и AFFILIATE_MARKER

python -m flypingavia
```

Сервер Mini App поднимается на `WEBAPP_PORT` (по умолчанию `8080`).

### Telegram Mini App

**Development (временный tunnel):**

1. Поднимите HTTPS-туннель к локальному порту:
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8080
   # или: ngrok http 8080
   ```
2. В `.env`:
   ```env
   APP_ENV=development
   WEBAPP_URL=https://your-tunnel.example
   ```
3. Перезапустите бота — кнопка **🛩 Открыть приложение** (только если URL — публичный HTTPS).
4. Temporary `*.trycloudflare.com` — **только для разработки**, не production.
   При `APP_ENV=production` такой URL отклоняется (`Settings` + `supervise.sh`, exit ≠ 0).

**Production (постоянный HTTPS):**

Схема: `Telegram → https://app.example.com → proxy → 127.0.0.1:8080`.

1. DNS A/AAAA или CNAME на сервер (или named Cloudflare Tunnel на **постоянном** custom hostname).
2. Reverse proxy: примеры в `deploy/caddy/` или `deploy/nginx/`.
3. `.env`:
   ```env
   APP_ENV=production
   WEBAPP_URL=https://app.example.com
   WEBAPP_DEV_USER_ID=0
   TRAVELPAYOUTS_TOKEN=…
   FORWARDED_ALLOW_IPS=127.0.0.1
   ```
   Не используйте `*.trycloudflare.com` — запуск завершится ошибкой.
4. Проверьте:
   ```bash
   curl -sf https://app.example.com/api/ready
   ```
5. BotFather (вручную, без вставки токена в чаты/доки):
   - `/setmenubutton` → бот → название кнопки → точный `WEBAPP_URL` (только HTTPS);
   - при необходимости `/setdomain` → hostname из `WEBAPP_URL`;
   - открыть Mini App из Telegram.
6. Полный чеклист: [docs/PRODUCTION_CHECKLIST.md](docs/PRODUCTION_CHECKLIST.md).

Автоперезапуск:

```bash
./scripts/supervise.sh
```

- `APP_ENV=production` — **не** генерирует новый tunnel URL и **не** переписывает `WEBAPP_URL`; при ошибке конфигурации **завершается с кодом ≠ 0**.
- `development` — optional quick tunnel + обновление URL (как раньше).
Локальный просмотр UI в браузере (без Telegram):
```env
APP_ENV=development
WEBAPP_DEV_USER_ID=1
```
и откройте `http://127.0.0.1:8080/`. В **production** `WEBAPP_DEV_USER_ID` должен быть `0`: вход только через подписанный Telegram `initData` (`Authorization: tma …`). Подробности — [docs/SECURITY.md](docs/SECURITY.md).

**Smoke auth (WA-03):** открыть Mini App из Telegram → создать Watch → закрыть/открыть снова → открыть URL в браузере (должен быть экран «внутри Telegram») → поддельный initData даёт `401`.

Docker:

```bash
docker build -t flypingavia .
docker run --env-file .env -p 127.0.0.1:8080:8080 -v "$(pwd)/data:/app/data" flypingavia
```

Пример compose: `deploy/docker-compose.production.example.yml`.

## Deep links (TG-03)

Ссылки вида `https://t.me/<bot>?start=<payload>` сохраняют источник перехода (first/last touch).

Примеры (замените `FlyPingBot` на ваш username из `TELEGRAM_BOT_USERNAME`):

```text
https://t.me/FlyPingBot?start=site
https://t.me/FlyPingBot?start=telegram_post
https://t.me/FlyPingBot?start=partner_blog
```

- payload: только буквы/цифры/`_`/`-`, максимум **64** символа;
- payload **виден** пользователю в URL — не кладите секреты;
- обычный `/start` без payload не стирает последний источник.

Подробности: [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md).

### Поделиться подпиской (TG-04)

В карточке подписки — «Поделиться»: создаётся ссылка `?start=share_…` (7 дней, до 20 копий).  
Получатель подтверждает копию через подписанный callback; в attribution пишется `share`, не raw token.  
См. [docs/WATCH_SHARING.md](docs/WATCH_SHARING.md).

### Health-алерты админу (RL-03)

При системных сбоях (БД, провайдер, stalled checker, Telegram API, readiness) бот пишет админу в `ADMIN_TELEGRAM_CHAT_ID` с threshold/cooldown и recovery. См. [docs/HEALTH_MONITORING.md](docs/HEALTH_MONITORING.md).

## Команды бота

| Команда | Описание |
|---------|----------|
| `/watch MOW IST 15000 2026-09-10` | Следить за маршрутом (дата опциональна) |
| `/list` | Список подписок |
| `/unwatch 1` | Удалить подписку |
| `/check` | Проверить цены сейчас |
| `/help` | Справка |

Коды аэропортов — IATA латиницей (`MOW`, `LED`, `AYT`, `IST`, `DXB`…).

## Конфигурация

См. `.env.example`. Поддерживаются оба стиля имён:

| Наше имя | Ваш алиас | Назначение |
|----------|-----------|------------|
| `BOT_TOKEN` | `TELEGRAM_TOKEN` | Токен Telegram-бота |
| `APP_ENV` | — | `development` / `production` / `test` |
| `WEBAPP_URL` | — | Canonical HTTPS Mini App URL (обязателен в production) |
| `FORWARDED_ALLOW_IPS` | — | IP reverse proxy для X-Forwarded-* (default `127.0.0.1`) |
| `TRAVELPAYOUTS_TOKEN` | `AVIASALES_API_TOKEN` | API цен |
| `CHECK_INTERVAL_MINUTES` | `CHECK_INTERVAL_SECONDS` | Интервал проверки |
| `DATABASE_URL` | `DB_PATH` | SQLite |
| `CURRENCY` | — | Валюта (по умолчанию `rub`) |
| `DISPLAY_TIMEZONE` | — | IANA timezone для показа времени проверки (default `Europe/Moscow`) |
| `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS` | — | Срок жизни WebApp initData (default `3600`) |
| `TELEGRAM_BOT_USERNAME` | — | Username бота без `@` (кнопка вне Telegram; опционально) |
| `AFFILIATE_MARKER` | — | Маркер CPA в ссылках |
| `TRAVELPAYOUTS_SEARCH_MARKER` | — | Числовой partner ID для Flight Search |
| `LIVE_SEARCH_MODE` | `multi` | `off` / `multi` / `always` |
| `FREE_WATCH_LIMIT` | — | Лимит маршрутов (0 = без лимита) |

Файл `.env` в git не коммитится.

## Тесты

```bash
pip install -r requirements.txt
pytest -q
```

## Монетизация и стратегия

Кратко: **Affiliate / CPA** уже в алертах и карточках. Freemium/подписка/B2B — стратегия, не runtime.

Актуальная версия: [docs/MONETIZATION.md](docs/MONETIZATION.md), план этапов — [docs/MASTER_ROADMAP.md](docs/MASTER_ROADMAP.md), метрики — [docs/KPI.md](docs/KPI.md).

> Замечание: `FREE_WATCH_LIMIT` есть в конфиге, но в handlers/API сейчас **не применяется** (см. [docs/DECISIONS.md](docs/DECISIONS.md)).

## Стек

- Python 3.11+
- aiogram 3
- SQLAlchemy 2 + aiosqlite
- APScheduler
- httpx (Travelpayouts)
- pydantic-settings

## Структура

```
docs/                  # продуктовая документация (точка входа: docs/README.md)
flypingavia/
  bot/                 # Telegram handlers / keyboards / formatters
  api/                 # FastAPI Mini App + auth
  web/static/          # UI Mini App
  db/                  # User, Watch
  services/            # prices, checker, locations, flight_search
  main.py              # бот + scheduler + uvicorn
scripts/               # supervise (автоперезапуск)
```

Подробнее: [docs/TECH_ARCHITECTURE.md](docs/TECH_ARCHITECTURE.md).

## Статус

Текущая версия приложения: **0.3.1** (бот + Mini App + auth + CS/NT/TR пакет).  
Запуск с `BOT_TOKEN`. Без `TRAVELPAYOUTS_TOKEN` — demo-цены.  
История: [docs/CHANGELOG.md](docs/CHANGELOG.md).

### Ручной git tag (после merge и production smoke)

> Выполнять только после merge и успешного production smoke test.  
> Команды **не** запускаются автоматически агентом/CI.

```bash
git tag -a v0.3.1 -m "FlyPingAvia 0.3.1"
git push origin v0.3.1
```

Tag в репозитории на момент документации может ещё не существовать.

