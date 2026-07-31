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

Таблица `system_health_incidents` (миграции `005_rl03_health_incidents.sql`, `006_rl03_recovery_delivery.sql`).

| Key | Смысл |
|-----|--------|
| `database_unavailable` | `SELECT 1` не проходит |
| `provider_unavailable` | системные ошибки провайдера в checker |
| `checker_stalled` | устаревший heartbeat при активных Watch |
| `checker_crashed` | unexpected exception в scheduler job (`run_checker_job`) |
| `telegram_delivery_failure` | системные сбои доставки price alerts |
| `webapp_unavailable` | production Mini App / local health |
| `readiness_failed` | production readiness issues |

Heartbeat: `system_runtime_state` (`component_key=price_checker`).

### Статусы incident

| Status | Смысл |
|--------|--------|
| `open` | сбой активен |
| `recovery_pending` | восстановление обнаружено; recovery alert ещё не доставлен |
| `recovered` | закрыт после успешной доставки recovery (или без alert, если failure не уходил) |

Поле `recovery_notified_at` фиксирует успешную доставку recovery. Pending recovery хранится в БД и **переживает restart**.

## Database outage fallback

Если основная БД недоступна, записать incident в неё невозможно. Для **только** `database_unavailable` используется process-local `DatabaseOutageTracker` (`flypingavia/monitoring/db_fallback.py`):

- threshold / cooldown как у обычных incidents (`ADMIN_ALERT_*`);
- admin alert уходит без записи в БД;
- состояние **не** пишется на диск и **не** переживает полный process restart (счётчик сбрасывается — ожидаемо);
- после успешного `SELECT 1` история синхронизируется в `system_health_incidents` (recovered), если возможно;
- остальные ключи incidents по-прежнему требуют БД.

Ошибка DB check **не** прерывает остальные проверки итерации monitor (`_run_check_safely`).

## Checker crash wrapper

APScheduler job `price_check` вызывает `run_checker_job`, а не `checker.run_once` напрямую:

- unexpected exception → heartbeat `mark_checker_error` + incident `checker_crashed` (summary = `type(exc).__name__`);
- traceback только в server log;
- следующий успешный `run_once` → recovery;
- штатные provider errors внутри checker **не** становятся `checker_crashed`.

## Anti-spam

| Env | Default |
|-----|---------|
| `ADMIN_ALERT_FAILURE_THRESHOLD` | 3 (1–100) |
| `ADMIN_ALERT_COOLDOWN_SECONDS` | 3600 (60–86400) |

Cooldown failure **не** блокирует recovery.  
Recovery считается завершённой **только после успешной доставки**; при ошибке Telegram состояние `recovery_pending` сохраняется и повторяется.

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

`open_incidents` считает `open` + `recovery_pending`.  
Без текстов ошибок, chat id, credentials.

## Команда

`/admin_health` — только для user id из `ADMIN_TELEGRAM_USER_IDS` или личного `ADMIN_TELEGRAM_CHAT_ID`.

Sentry / Grafana / PagerDuty **не** используются.
