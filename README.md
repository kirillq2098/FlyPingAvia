# FlyPingAvia

Telegram-бот для мониторинга цен на авиабилеты.

Пользователь задаёт маршрут и порог цены — бот следит за предложениями и присылает алерт, когда билет стал дешевле. В алертах — партнёрская ссылка (CPA).

## MVP 0.1.0

Уже есть:

- команды `/start`, `/help`, `/watch`, `/list`, `/unwatch`, `/check`
- SQLite-хранилище подписок
- лимит бесплатного тарифа (по умолчанию 2 маршрута)
- фоновая проверка цен (APScheduler)
- цены через Travelpayouts API или **demo-режим** без токена
- партнёрские ссылки Aviasales с `marker`

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

См. `.env.example`:

| Переменная | Назначение |
|------------|------------|
| `BOT_TOKEN` | Токен Telegram-бота |
| `TRAVELPAYOUTS_TOKEN` | API-токен; пусто = demo-цены |
| `AFFILIATE_MARKER` | Маркер CPA в ссылках |
| `FREE_WATCH_LIMIT` | Лимит маршрутов free-тира |
| `CHECK_INTERVAL_MINUTES` | Интервал фоновой проверки |
| `DATABASE_URL` | SQLite / будущий Postgres |

## Тесты

```bash
pip install -r requirements.txt
pytest -q
```

## Монетизация (стратегия)

1. **Affiliate / CPA** — ссылки в алертах (уже в MVP).
2. **Freemium** — лимит маршрутов сейчас; платная подписка позже.
3. **B2B / API** — после стабильного B2C.
4. Доп. услуги (страховки, отели) — после трафика.

Подробнее: масштабирование по данным/продукту/каналам, roadmap и метрики ниже.

### Масштабирование

| Слой | Что делать |
|------|------------|
| Данные | Несколько источников, кэш, умный polling |
| Продукт | Календарь дешевизны, гибкие даты, группы |
| Каналы | SEO-минисайт, шаринг алертов, блогеры |
| Удержание | Антиспам, пороги, «тихие часы» |
| Юнит-экономика | CAC, LTV, alert → клик → покупка |

### Roadmap

1. MVP (этот релиз) — бот + партнёрка + лимит free.
2. Юнит-экономика — измерить конверсию алертов.
3. Подписка — платные лимиты и приоритет.
4. Надёжность данных и антиспам.
5. B2B / API.

## Стек

- Python 3.11+
- aiogram 3
- SQLAlchemy 2 + aiosqlite
- APScheduler
- httpx (Travelpayouts)
- pydantic-settings

## Структура

```
flypingavia/
  bot/handlers.py      # команды Telegram
  db/models.py         # User, Watch
  db/repository.py     # CRUD подписок
  services/prices.py   # demo + Travelpayouts + affiliate URL
  services/checker.py  # фоновые алерты
  main.py              # точка входа
```

## Статус

MVP 0.1.0 готов к запуску с `BOT_TOKEN`. Без `TRAVELPAYOUTS_TOKEN` работает на demo-ценах — удобно для разработки и демо.
