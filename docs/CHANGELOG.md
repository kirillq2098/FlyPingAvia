# Changelog — FlyPingAvia

Связанные документы: [Architecture](TECH_ARCHITECTURE.md) · [Decisions](DECISIONS.md) · [Roadmap](MASTER_ROADMAP.md)

История по значимым коммитам ветки продукта. Формат близкий к Keep a Changelog; версии — по смыслу релизов в git, не по тегам (тегов в репозитории на момент составления не зафиксировано).

## [Unreleased]

### Documentation

- Папка `docs/`: vision, roadmap, architecture, monetization, marketing, decisions, KPI, changelog.

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
