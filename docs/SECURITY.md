# Security — FlyPingAvia

Связанные документы: [TECH_ARCHITECTURE](TECH_ARCHITECTURE.md) · [PRODUCTION_CHECKLIST](PRODUCTION_CHECKLIST.md)

## Mini App: без логина и пароля

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
