# Decisions — FlyPingAvia

Связанные документы: [Vision](PRODUCT_VISION.md) · [Architecture](TECH_ARCHITECTURE.md) · [Changelog](CHANGELOG.md) · [Roadmap](MASTER_ROADMAP.md)

Журнал решений, которые **уже отражены в коде или явных комментариях**.  
Новые решения добавлять сверху таблицы с датой.

## Формат

`Дата | Решение | Почему | Где в коде | Статус`

---

## Принятые решения

| Дата (по git / факт) | Решение | Почему | Где | Статус |
|----------------------|---------|--------|-----|--------|
| 2026-07 (WA-02) | `APP_ENV` + canonical HTTPS `WEBAPP_URL`; temp trycloudflare только development; production supervise не переписывает URL | Ephemeral URL ломает Telegram кнопку | `config.py`, `webapp_url.py`, `scripts/supervise.sh`, `deploy/*` | Active (Partial ops — нужен живой домен) |
| 2026-07 (WA-02) | Same-origin Mini App+API; CORS middleware не добавляем | Static и `/api` с одного origin за reverse proxy | `api/app.py`, docs | Active |
| 2026-07 (WA-02) | Uvicorn `proxy_headers` + `FORWARDED_ALLOW_IPS=127.0.0.1` (не `*`) | Canonical URL из env, не из Host | `main.py` | Active |
| 2026-07 (коммит `f7bbabf` и след.) | UI пассажиров скрыт; всегда 1 взрослый | Нет доступа к Flight Search API у партнёра; кэш Data API не даёт корректную цену за состав | `handlers.py` (`_continue_to_preview`), Mini App `#pax-block` hidden, `app.js` | Active |
| 2026-07 (`91e516d`) | One-way на дату брать из month-matrix, не из `prices/cheap` | `cheap` отдавал нерелевантный/кэш RT | `prices.py` (CHEAP_URL не вызывается для dated OW) | Active |
| 2026-07 (`d2659c8`) | Не умножать кэш-цену Data API на число пассажиров | Цена в кэше за 1 взрослого | `prices.py` | Active |
| 2026-07 (`c392b09` + позже) | Хранить `return_date` и pax-поля в `Watch` | Подготовка к RT и будущему live search | `models.py`, API `WatchIn` | Active (pax UI off) |
| 2026-07 (`03c1846`) | Не ставить MenuButtonWebApp с tunnel URL | Telegram кэширует URL → Error 1033 | `main.py` → `MenuButtonCommands`; WebApp через кнопки `/start` | Active |
| 2026-07 (`91ed030`) | Убрать лимиты маршрутов | На этапе роста MVP | handlers/API без проверки; `FREE_WATCH_LIMIT` остался в конфиге | Active (конфиг-долг) |
| 2026-07 (`541e466`) | Mini App как основной UI поиска/подписок рядом с ботом | Удобнее формы, чем чистый чат | `api/app.py`, `web/static/*` | Active |
| 2026-07 (`fa04c96`) | Watchdog supervise для бота + cloudflared | Сервис падал вместе с ephemeral tunnel | `scripts/supervise.sh` | Active |
| — | Без `TRAVELPAYOUTS_TOKEN` — demo prices | Можно поднимать бота и UI без ключа | `config.is_demo_prices`, `DemoPriceProvider` | Active |
| — | Алерт при `price <= max_price` | Простое правило порога | `checker.py` | Active |
| — | Soft-delete подписок (`is_active=False`) | Не терять историю строк | `repository.deactivate_watch` | Active |
| — | Auth Mini App через Telegram initData HMAC | Стандарт WebApp | `telegram_auth.py` | Active |

## Открытые решения (нужен выбор)

| Тема | Варианты | Блокирует | TODO-вопрос |
|------|----------|-----------|-------------|
| Freemium | Включить `FREE_WATCH_LIMIT` / убрать из доков / оставить 0 навсегда | Честность README и монетизация | Какой лимит и когда? |
| Повторные алерты | Алертить каждый цикл / только если цена изменилась / cooldown | Шум в UX | Использовать ли `last_alert_price`? |
| Live Search | Ждать доступ партнёра / искать другой источник / остаться на 1 взрослом | UI пассажиров, «семейные» цены | Когда снова включаем pax UI? |
| Хостинг Mini App | **Целевой:** свой домен или named Cloudflare Tunnel + `APP_ENV=production`. Quick tunnel — только development | Надёжность кнопки | Checklist: `docs/PRODUCTION_CHECKLIST.md` |
| Версионирование | Выровнять всё на 0.2.0 / оставить `__init__` 0.1.0 до релиза | Документы и ожидания | Когда считаем релиз «официальным»? |

## Как обновлять этот файл

1. Любое продуктовое «больше так не делаем» → новая строка в таблице.  
2. Если решение отменено — статус `Superseded` + ссылка на новое.  
3. Не записывать сюда идеи без внедрения в код (им место в [MASTER_ROADMAP](MASTER_ROADMAP.md)).
