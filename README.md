# FlyPingAvia

Telegram-бот для мониторинга цен на авиабилеты.

Пользователь задаёт маршрут и порог цены — бот следит за предложениями и присылает алерт, когда билет стал дешевле. В алертах — партнёрская ссылка (CPA).

## Документация

Точка входа: **[docs/README.md](docs/README.md)**

| Документ | Содержание |
|----------|------------|
| [Product Vision](docs/PRODUCT_VISION.md) | Зачем продукт и что уже умеет |
| [Strategy](docs/FLYPING_STRATEGY.md) | USP, рост 100→100k, non-goals |
| [Master Roadmap](docs/MASTER_ROADMAP.md) | Этапы развития и открытые вопросы |
| [Competitive Analysis](docs/COMPETITIVE_ANALYSIS.md) | Конкуренты и opportunities |
| [Tech Architecture](docs/TECH_ARCHITECTURE.md) | Стек, модули, API, данные |
| [Monetization](docs/MONETIZATION.md) | CPA в коде и стратегия дальше |
| [Marketing](docs/MARKETING.md) | Каналы и ограничения |
| [Decisions](docs/DECISIONS.md) | Зафиксированные решения |
| [Changelog](docs/CHANGELOG.md) | История изменений |
| [KPI](docs/KPI.md) | Метрики по этапам |

## MVP 0.2.0

Уже есть:

- Telegram Mini App (веб-приложение внутри Telegram)
- команды и кнопки меню: приложение / добавить / маршруты / проверить / помощь
- города словами + поиск по всем аэропортам (самый дешёвый)
- вилка цен: дёшево / обычно / дорого + кнопки выбора порога
- SQLite-хранилище подписок
- фоновая проверка цен (APScheduler)
- цены через Travelpayouts API или **demo-режим** без токена
- партнёрские ссылки Aviasales с `marker`
- живой поиск за взрослых/детей (Flight Search API, если Travelpayouts выдал доступ)

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

1. Поднимите HTTPS-туннель к локальному порту, например:
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8080
   # или: ngrok http 8080
   ```
2. Пропишите URL в `.env`:
   ```env
   WEBAPP_URL=https://your-tunnel.example
   ```
3. Перезапустите бота — появится кнопка **🛩 Открыть приложение**.
4. В @BotFather можно также привязать домен: `/setdomain`.

Автоперезапуск (бот + туннель), если сервис падает:

```bash
./scripts/supervise.sh
# или в фоне:
# tmux new-session -d -s flypingavia-supervise './scripts/supervise.sh'
```

Watchdog сам рестартит `python -m flypingavia` и `cloudflared`, при новом URL туннеля обновляет `WEBAPP_URL` в `.env` и перезапускает бота. Логи: `/tmp/flypingavia/`.

Локальный просмотр UI в браузере (без Telegram):
```env
WEBAPP_DEV_USER_ID=1
```
и откройте `http://127.0.0.1:8080/`.

Docker:

```bash
docker build -t flypingavia .
docker run --env-file .env -v "$(pwd)/data:/app/data" flypingavia
```

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
| `TRAVELPAYOUTS_TOKEN` | `AVIASALES_API_TOKEN` | API цен |
| `CHECK_INTERVAL_MINUTES` | `CHECK_INTERVAL_SECONDS` | Интервал проверки |
| `DATABASE_URL` | `DB_PATH` | SQLite |
| `CURRENCY` | — | Валюта (по умолчанию `rub`) |
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

MVP **0.2.0** (бот + Mini App). Запуск с `BOT_TOKEN`. Без `TRAVELPAYOUTS_TOKEN` — demo-цены.  
История: [docs/CHANGELOG.md](docs/CHANGELOG.md).

