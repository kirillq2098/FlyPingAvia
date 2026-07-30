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

## Срок и лимиты

| Параметр | Default | Env |
|----------|---------|-----|
| TTL | 168 ч (7 дней) | `WATCH_SHARE_TTL_HOURS` (1–720) |
| Max uses | 20 успешных копий | `WATCH_SHARE_MAX_USES` (1–1000) |
| Активных ссылок на Watch | 10 | при 11-й отзывается самая старая |

Preview **не** увеличивает `used_count`. Повторный confirm того же пользователя идемпотентен.

## Безопасность

Получатель не видит: owner Telegram ID/username, Watch ID, историю цен, алерты.  
Истёкшая / отозванная / исчерпанная / чужая ссылка → единое сообщение без деталей.  
Owner, открывший свою ссылку: «Это ваша подписка — копия не требуется.»

TG-03 attribution сохраняет полный payload `share_…` как `last_start_source`.

## Отзыв

Telegram: «Отозвать ссылки» · API: `DELETE /api/watches/{id}/shares`.

Referral rewards, dashboard и analytics **не реализованы**.
