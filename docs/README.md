# Документация FlyPingAvia

Точка входа в продуктовые и технические документы проекта.

**Продукт сейчас:** Telegram-бот + Mini App для мониторинга цен на авиабилеты.  
**Версия в репозитории:** `0.3.1` (`pyproject.toml` → `flypingavia.__version__` / `/api/health` / CLI `--version`). См. [CHANGELOG](CHANGELOG.md), [RL-02](FEATURE_BACKLOG.md).

## Карта документов

| Документ | О чём |
|----------|--------|
| [PRODUCT_VISION.md](PRODUCT_VISION.md) | Зачем продукт, для кого, что уже умеет |
| [FLYPING_STRATEGY.md](FLYPING_STRATEGY.md) | Долгосрочная стратегия: USP, рост, non-goals |
| [FEATURE_BACKLOG.md](FEATURE_BACKLOG.md) | Реестр функций, релизы, Impact vs Effort |
| [SPRINT_01.md](SPRINT_01.md) | План текущего спринта (ожидает подтверждения) |
| [USER_JOURNEY.md](USER_JOURNEY.md) | Путь пользователя и точки отказа |
| [MASTER_ROADMAP.md](MASTER_ROADMAP.md) | Этапы развития и открытые вопросы по цели |
| [COMPETITIVE_ANALYSIS.md](COMPETITIVE_ANALYSIS.md) | Конкуренты, таблица сравнения, opportunities |
| [TECH_ARCHITECTURE.md](TECH_ARCHITECTURE.md) | Стек, модули, API, данные, деплой |
| [SECURITY.md](SECURITY.md) | Auth Mini App (initData), изоляция, smoke |
| [MONETIZATION.md](MONETIZATION.md) | Что уже в коде и что только в стратегии |
| [MARKETING.md](MARKETING.md) | Каналы; блогер-кит → [BLOGGER_KIT.md](BLOGGER_KIT.md) |
| [BLOGGER_KIT.md](BLOGGER_KIT.md) | GR-02: тексты, deep links, FAQ, checklist для блогеров |
| [DECISIONS.md](DECISIONS.md) | Зафиксированные продуктовые/технические решения |
| [CHANGELOG.md](CHANGELOG.md) | История изменений по коммитам |
| [COPY_GUIDE.md](COPY_GUIDE.md) | USP «сторож цены», glossary, fixed copy |
| [ATTRIBUTION.md](ATTRIBUTION.md) | Deep-link start payload, first/last touch |
| [WATCH_SHARING.md](WATCH_SHARING.md) | Share подписки через `share_<token>` |
| [HEALTH_MONITORING.md](HEALTH_MONITORING.md) | RL-03 admin health alerts |
| [DEPLOY_TIMEWEB.md](DEPLOY_TIMEWEB.md) | Production deploy на Timeweb VPS |
| [KPI.md](KPI.md) | Какие метрики уже можно считать; чего не хватает |

## Быстрый ориентир «что есть / чего нет»

**Есть в продукте (код):**

- бот (aiogram): `/start`, `/help`, `/watch`, `/list`, `/unwatch`, `/check`, `/add` + reply/inline-кнопки;
- Mini App: поиск маршрута, вилка цен, подписки;
- one-way и round-trip (сумма двух one-way или Flight Search при доступе);
- порог цены + пресеты «дёшево» / «обычно»;
- фоновые алерты (APScheduler);
- цены Travelpayouts Data API или demo без токена;
- партнёрские ссылки Aviasales (`AFFILIATE_MARKER`);
- watchdog `scripts/supervise.sh` (бот + cloudflared).

**Есть в конфиге / README, но не enforced в runtime:**

- `FREE_WATCH_LIMIT` — поле настроек есть, лимит в handlers/API **не применяется**;
- платные подписки, B2B/API, SEO-сайт — только текст стратегии в корневом README.

**Скрыто / отключено по решению:**

- UI выбора взрослых/детей/младенцев (нужен доступ к Flight Search API);
- кнопка MenuButtonWebApp в Telegram (URL туннеля кэшировался) — WebApp через кнопки после `/start`.

## Как пользоваться этой папкой

1. Новая идея → сначала [PRODUCT_VISION](PRODUCT_VISION.md), [FLYPING_STRATEGY](FLYPING_STRATEGY.md), [COMPETITIVE_ANALYSIS](COMPETITIVE_ANALYSIS.md) и [DECISIONS](DECISIONS.md); затем карточка в [FEATURE_BACKLOG](FEATURE_BACKLOG.md).
2. UX и воронка → [USER_JOURNEY](USER_JOURNEY.md).
3. План работ → [FEATURE_BACKLOG](FEATURE_BACKLOG.md) + [SPRINT_01](SPRINT_01.md) + [MASTER_ROADMAP](MASTER_ROADMAP.md) + [KPI](KPI.md).
4. Изменение кода/инфры → [TECH_ARCHITECTURE](TECH_ARCHITECTURE.md), запись в [CHANGELOG](CHANGELOG.md).
5. Деньги и рост → [MONETIZATION](MONETIZATION.md), [MARKETING](MARKETING.md).

Корневой [README.md](../README.md) — быстрый старт для разработчика. Эта папка — карта продукта и компании.
