# Attribution — Telegram deep links (TG-03)

Связанные документы: [SECURITY](SECURITY.md) · [USER_JOURNEY](USER_JOURNEY.md) · [FEATURE_BACKLOG](FEATURE_BACKLOG.md)

## Deep link

```text
https://t.me/<bot_username>?start=<payload>
```

Примеры (замените username на реальный из `TELEGRAM_BOT_USERNAME`):

```text
https://t.me/FlyPingBot?start=site
https://t.me/FlyPingBot?start=telegram_post
https://t.me/FlyPingBot?start=partner_blog
```

Helper в коде: `flypingavia.bot.start_payload.build_telegram_start_link`.

## Payload

- Алфавит: `[A-Za-z0-9_-]`
- Длина: 1–64
- Case сохраняется как пришёл
- **Не секрет:** payload виден в URL и в Telegram
- Не исполняется как команда / callback
- Невалидный payload → как отсутствие (без ошибки пользователю)

Зарезервированные префиксы (`src_`, `cmp_`, `share_`):

- обычные payload (`site`, `instagram`, …) сохраняются **полностью**;
- payload вида `share_<token>` (TG-04) сохраняется в attribution **только как** `share` — raw token **не** пишется в `first_start_source` / `last_start_source` (см. [WATCH_SHARING](WATCH_SHARING.md), helper `attribution_source_for_start_payload`).

## First-touch / last-touch

| Поле | Смысл |
|------|--------|
| `first_start_source` | Первый валидный attribution source (не перезаписывается) |
| `last_start_source` | Последний валидный attribution source |
| `first_start_at` | Первый `/start` (UTC) |
| `last_start_at` | Последний `/start` (UTC) |

Правила:

- `/start` без payload **не стирает** `last_start_source`
- невалидный payload обрабатывается как отсутствие
- share deep link → source = `share` (не полный `share_<token>`)
- открытие Mini App (WA-03) **не** заполняет start attribution
- A/B analytics и dashboard **не реализованы**

## SQL-пример (не dashboard)

```sql
SELECT first_start_source, COUNT(*) AS users
FROM users
GROUP BY first_start_source
ORDER BY users DESC;
```

## Миграция

`scripts/migrations/003_tg03_user_start_attribution.sql` + авто-ALTER в `init_db` для SQLite.  
Alembic в репозитории не используется (единый стиль с 001/002).
