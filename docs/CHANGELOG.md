# Changelog — FlyPingAvia

Связанные документы: [Architecture](TECH_ARCHITECTURE.md) · [Decisions](DECISIONS.md) · [Roadmap](MASTER_ROADMAP.md)

История по значимым коммитам ветки продукта. Формат близкий к Keep a Changelog; версии — по смыслу релизов в git, не по тегам (тегов в репозитории на момент составления не зафиксировано).

## [Unreleased]

### Added

- **AN-03:** таблица `alert_events` — лог успешных алертов; `repo.count_alerted_watchers`; SQL `scripts/kpi_alerted_watchers.sql`; миграция `scripts/migrations/001_alert_events.sql`.
- **NT-04:** антиспам алертов — `NOTIFICATION_COOLDOWN_HOURS` (default 24) и `MIN_PRICE_DELTA` (default 500); решение по истории `AlertEvent` (`notify_policy.decide_notification`); `last_alert_price` обновляется только после успешной отправки.
- **NT-02:** явный контракт порога в алерте — `format_threshold_contract` / `threshold_contract=True` в `format_price_card`; блок «Текущая цена / Ваш порог / X ≤ Y / Выгода к порогу».
- **NT-03:** рыночная оценка в алерте — `format_market_assessment` (🟢/🟡/🔴 + ориентир «около typical»); порядок: NT-02 → рынок; fallback при `band=None`; аудит существующего `get_trip_band`/`align_band_to_quote`/`format_band_block`.
- **CS-05:** предупреждение порога ниже рынка — `threshold_policy.should_warn_low_threshold` (`threshold < cheap_max`); подтверждение в Telegram FSM и Mini App (`confirm_low_threshold` / HTTP 409).
- **CS-07 MVP:** flexible date window ±1/±3/±7 days — поле `Watch.flexibility_days`, `flexible_dates` / `search_flexible_trip`, FSM + Mini App, checker ищет минимум по окну.
- **TR-04:** время последней проверки — `format_last_checked` / `DISPLAY_TIMEZONE` (default `Europe/Moscow`); показ в Telegram-карточке, алерте и Mini App; `WatchOut.last_checked_at` (UTC ISO); обновление после каждой завершённой проверки (в т.ч. Quote=None), не при ошибке поиска.
- **WA-02 (код):** `APP_ENV` + строгая валидация canonical `WEBAPP_URL`; `/api/health` readiness + `/api/ready`; Telegram-кнопка только на публичный HTTPS; reverse-proxy/compose/cloudflared examples; production checklist. Статус Feature — Partial до живого домена.

### Fixed

- **NT-04 review fixes:** `asyncio.Lock` против параллельных `run_once`; раздельные ошибки Telegram send vs persistence `AlertEvent`; валидация `NOTIFICATION_COOLDOWN_HOURS` / `MIN_PRICE_DELTA` ≥ 0 при старте.
- **CS-05 review fix:** восстановление pending threshold при ошибке создания Watch.
- **CS-07 review fix:** единый flexible band для `/api/quote` и `POST /api/watches`.

### Documentation

- Папка `docs/`: vision, strategy, feature backlog, user journey, sprint 01, roadmap, competitive analysis, architecture, monetization, marketing, decisions, KPI, changelog.

## [0.2.0] — 2026-07

Ориентир: `pyproject.toml` / FastAPI `version="0.2.0"`, README «MVP 0.2.0».

### Added

- Telegram Mini App: поиск, вилка цен, подписки (`feat: Telegram Mini App…`)
- Города словами и поиск по аэропортам города
- Кнопки меню, карточки маршрутов, вилка дёшево/обычно/дорого
- Пассажиры и билет туда–обратно в модели/потоках (позже UI pax скрыт)
- Код живого поиска Flight Search API (`feat: живой поиск…`)
- Watchdog `scripts/supervise.sh` + `start-supervise.sh`
- Декоративный «бумажный самолётик» в Mini App

### Changed

- Тексты `/start` и `/help`, структура сообщений и карточек цен
- One-way цена на дату из month-matrix
- Не умножать кэш-цену на пассажиров
- Скрыт выбор взрослых/детей в боте и Mini App

### Fixed

- Порог «своя цена» без ложной валидации step
- Стабильнее Mini App в мобильном WebView
- Кнопка Mini App при заданном `WEBAPP_URL`
- Не кэшировать tunnel URL в menu button
- Самолёт: z-index и полёт в пределах экрана

### Notes

- `flypingavia.__version__` всё ещё `0.1.0` (рассинхрон с pyproject).

## [0.1.0] — 2026-07

### Added

- MVP Telegram-бот мониторинга цен (`feat: MVP 0.1.0`)
- Поддержка алиасов env: `TELEGRAM_TOKEN`, `AVIASALES_API_TOKEN`
- README с продуктом и черновой стратегией монетизации
- Demo-режим без Travelpayouts token
- Affiliate URL с marker

### Changed

- Убраны лимиты маршрутов (`feat: убрать лимиты…`)

## Как вести дальше

- При мерже фичи — короткая запись в `[Unreleased]`
- При релизе — перенос в секцию версии и выравнивание `__version__` / pyproject / README Status

**TODO:**

- [ ] Нужны ли git tags `v0.1.0`, `v0.2.0`?
- [ ] Публичный CHANGELOG только здесь или дублировать в Releases GitHub?
