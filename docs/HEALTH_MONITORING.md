# Health Monitoring — RL-03

Связанные документы: [PRODUCTION_CHECKLIST](PRODUCTION_CHECKLIST.md) · [SECURITY](SECURITY.md) · [FEATURE_BACKLOG](FEATURE_BACKLOG.md)

## Цель

Служебные Telegram-алерты администратору при системных сбоях и восстановлении.  
Не путать с пользовательскими price alerts (NT-04).

## Получатель

| Env | Default | Смысл |
|-----|---------|--------|
| `ADMIN_TELEGRAM_CHAT_ID` | пусто | User или group chat id; пусто = отправка выключена |
| `ADMIN_ALERTS_ENABLED` | `true` | Флаг; без chat id всё равно disabled |
| `ADMIN_TELEGRAM_USER_IDS` | пусто | CSV user id для `/admin_health` (если chat — группа) |

Startup лог: `Admin health alerts: enabled|disabled` (без chat id).

## Инциденты

Таблица `system_health_incidents` (миграция `005_rl03_health_incidents.sql`).

| Key | Смысл |
|-----|--------|
| `database_unavailable` | `SELECT 1` не проходит |
| `provider_unavailable` | системные ошибки провайдера в checker |
| `checker_stalled` | устаревший heartbeat при активных Watch |
| `checker_crashed` | зарезервировано |
| `telegram_delivery_failure` | системные сбои доставки price alerts |
| `webapp_unavailable` | production Mini App / local health |
| `readiness_failed` | production readiness issues |

Heartbeat: `system_runtime_state` (`component_key=price_checker`).

## Anti-spam

| Env | Default |
|-----|---------|
| `ADMIN_ALERT_FAILURE_THRESHOLD` | 3 (1–100) |
| `ADMIN_ALERT_COOLDOWN_SECONDS` | 3600 (60–86400) |

Recovery отправляется один раз, только если ранее ушёл failure alert.

## Telegram classification

Пользовательские (blocked / chat not found / deactivated) **не** открывают system incident.  
Системные (timeout, connection, 5xx, flood) — участвуют в threshold.

Ошибка отправки **admin** alert не создаёт рекурсивный `telegram_delivery_failure`.

## API

`/api/health` — без изменений тяжести.  
`/api/ready` добавляет минимальный summary:

```json
"health_monitor": { "status": "ok|degraded", "open_incidents": 0 }
```

Без текстов ошибок, chat id, credentials.

## Команда

`/admin_health` — только для user id из `ADMIN_TELEGRAM_USER_IDS` или личного `ADMIN_TELEGRAM_CHAT_ID`.

Sentry / Grafana / PagerDuty **не** используются.
