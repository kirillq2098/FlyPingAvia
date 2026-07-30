# Watch Sharing — TG-04

Связанные документы: [ATTRIBUTION](ATTRIBUTION.md) · [SECURITY](SECURITY.md) · [FEATURE_BACKLOG](FEATURE_BACKLOG.md)

## Смысл

Ссылка `https://t.me/<bot>?start=share_<token>` создаёт **копию** подписки у получателя.  
Оригинальный Watch остаётся у владельца; доступ к нему не передаётся.

## Token

- Формат payload: `share_<opaque>` (whitelist TG-03, ≤64 символов)
- Генерация: `secrets.token_urlsafe` (≥128 бит)
- В БД хранится только **SHA-256 hash**, raw token — нет
- Token ≠ Watch ID и не раскрывает структуру данных
- Attribution: в `users.*_start_source` пишется только `share` (не raw token)

## Confirm (proof-of-possession)

После `/start share_<token>` кнопки содержат HMAC proof:

```text
sc:<share_id>:<exp>:<signature>
```

- Подпись HMAC-SHA256 (`WATCH_SHARE_CALLBACK_SECRET`), truncate + base64url
- Привязка к Telegram user id получателя
- TTL: `WATCH_SHARE_CALLBACK_TTL_SECONDS` (default 900)
- Старый callback `share_confirm:<id>` отклоняется
- Clone только через `clone_watch_from_verified_share` после проверки proof

## Срок и лимиты

| Параметр | Default | Env |
|----------|---------|-----|
| TTL ссылки | 168 ч (7 дней) | `WATCH_SHARE_TTL_HOURS` (1–720) |
| Max uses | 20 успешных копий | `WATCH_SHARE_MAX_USES` (1–1000) |
| Активных ссылок на Watch | 10 | при 11-й отзывается самая старая |
| Callback proof TTL | 900 с | `WATCH_SHARE_CALLBACK_TTL_SECONDS` (60–3600) |

Preview **не** увеличивает `used_count`. Повторный confirm того же пользователя идемпотентен.

## Безопасность

Получатель не видит: owner Telegram ID/username, Watch ID, историю цен, алерты.  
Истёкшая / отозванная / исчерпанная / чужая / поддельный callback → единое сообщение без деталей.  
Owner, открывший свою ссылку: «Это ваша подписка — копия не требуется.»

Обычные deep-link payload сохраняются полностью. Share payload в attribution — только `"share"`. Секретная часть token не сохраняется.

## Отзыв

Telegram: «Отозвать ссылки» · API: `DELETE /api/watches/{id}/shares`.

Referral rewards, dashboard и analytics **не реализованы**.
