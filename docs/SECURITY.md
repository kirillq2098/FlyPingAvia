# Security — FlyPingAvia

Связанные документы: [TECH_ARCHITECTURE](TECH_ARCHITECTURE.md) · [PRODUCTION_CHECKLIST](PRODUCTION_CHECKLIST.md)

## Telegram deep-link attribution (TG-03)

`/start <payload>` сохраняет whitelist-строку `[A-Za-z0-9_-]{1,64}` в `users.first_start_source` / `last_start_source`.

Для share-ссылок TG-04 (`share_<token>`) в attribution пишется только `share` — **raw token не сохраняется**.

Не сохраняем: полный URL, IP, User-Agent, initData, referrer Mini App, произвольные query, текст сообщения, raw share token.

Payload **не секрет** (виден в URL) и **не исполняется** как команда. Подробности: [ATTRIBUTION.md](ATTRIBUTION.md).

## Watch sharing (TG-04)

Ссылка `?start=share_<token>` создаёт **копию** Watch у получателя, а не доступ к оригиналу.

- В URL только opaque token; raw token **не** хранится в БД (только SHA-256 `token_hash`; attribution = `share`).
- Confirm: HMAC callback proof `sc:<share_id>:<exp>:<sig>`, привязан к Telegram user id + TTL (`WATCH_SHARE_CALLBACK_SECRET`).
- Подбор `share_id` / старый `share_confirm:<id>` не создаёт Watch.
- Preview и confirm не раскрывают owner id/username, Watch id, историю цены, alert history.
- Чужой Watch при создании/отзыве share → `404`.
- Истёкший / отозванный / исчерпанный / неверный token / битый proof → одно безопасное сообщение без причины.
- Owner, открывший свою ссылку, видит preview, но копия не создаётся и `used_count` не растёт.
- Подробности: [WATCH_SHARING.md](WATCH_SHARING.md).

## Admin health alerts (RL-03)

Служебные алерты в `ADMIN_TELEGRAM_CHAT_ID` (не пользовательские price alerts).

- Состояние инцидентов в БД; без admin chat id в логах info и в `/api/health`/`/api/ready`.
- `/api/ready` показывает только `{status, open_incidents}` (`open` + `recovery_pending`).
- Пользовательские Telegram-ошибки (blocked/chat not found) не открывают system incident.
- Ошибка доставки admin alert не создаёт рекурсивный incident.
- Recovery закрывается только после успешной доставки (`recovery_pending` → `recovered`); pending переживает restart.
- `database_unavailable` при полной недоступности БД: process-local fallback (без записи секретов/URL); полный restart во время outage сбрасывает счётчик.
- Подробности: [HEALTH_MONITORING.md](HEALTH_MONITORING.md).

## Mini App Auth (WA-03)

Пользователь **не вводит** логин/пароль и не использует OAuth/JWT.

1. Telegram открывает Mini App и подписывает `Telegram.WebApp.initData` bot token’ом.
2. Frontend читает `initData` из текущего `window.Telegram.WebApp` и для каждого защищённого запроса к `/api/...` добавляет:

   ```http
   Authorization: tma <initData>
   ```

3. Backend (`flypingavia/api/telegram_auth.py`) проверяет подпись официальным алгоритмом Telegram (HMAC-SHA256, ключ `WebAppData`), сверяет `auth_date` и извлекает `user.id`.
4. Только этот id используется для доступа к Watch. Frontend user id, query `user_id`, body `telegram_user_id`, cookies и `initDataUnsafe` **не доверенные**.

## Срок жизни initData

- `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS` (default **3600**).
- Допустимый clock skew в будущем: **30 секунд**.
- Просроченный или «из будущего» initData → `401`. Автоматического refresh нет: нужно закрыть и снова открыть Mini App из Telegram.

## Режимы APP_ENV

| Режим | Поведение |
|-------|-----------|
| `production` | Только валидный initData. `WEBAPP_DEV_USER_ID` обязан быть `0`. |
| `development` | Без initData можно использовать `WEBAPP_DEV_USER_ID > 0`. Если initData передан и невалиден — `401`, **без** fallback на dev user. |
| `test` | Как development + FastAPI dependency override в тестах. |

## Что не логируем и не храним

Не пишем в логи/БД/storage: полную строку initData, Authorization header, bot token, hash, secret key, сырой user JSON.

`initData` не кладётся в URL, localStorage, sessionStorage, cookies.

## Ошибки

Защищённые endpoints отвечают `401` с безопасным JSON:

```json
{ "detail": { "code": "EXPIRED_INIT_DATA", "message": "…" } }
```

Коды: `MISSING_INIT_DATA`, `INVALID_INIT_DATA`, `INVALID_HASH`, `EXPIRED_INIT_DATA`, `FUTURE_AUTH_DATE`, `INVALID_TELEGRAM_USER`.

Чужой Watch → `404` (не `403`).

## Изоляция

Watch привязаны к внутреннему `users.id`, найденному по `telegram_id` из проверенного initData. Пользователь A не видит и не удаляет Watch пользователя B.

Telegram-бот по-прежнему доверяет `telegram_user_id` из aiogram update — это отдельный канал аутентификации, не HTTP Mini App.

## Ручной smoke (WA-03)

1. `APP_ENV=production`, валидный HTTPS `WEBAPP_URL`, `WEBAPP_DEV_USER_ID=0`.
2. Открыть Mini App из Telegram.
3. Проверить `GET /api/me` (через DevTools Network) — свой telegram_user_id.
4. Создать Watch.
5. Закрыть и снова открыть Mini App — Watch на месте.
6. Открыть тот же URL в обычном браузере — auth-gate, данные недоступны.
7. Подставить изменённый initData — сервер отвечает `401`.
