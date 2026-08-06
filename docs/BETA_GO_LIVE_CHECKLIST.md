# Beta Go-Live Checklist

Практические шаги запуска Closed Beta Phase A.  
Production и `main` не трогать без отдельного подтверждения.

Связано: [CLOSED_BETA_PLAYBOOK.md](CLOSED_BETA_PLAYBOOK.md)

Deep-link волны 1: `https://t.me/FlyPingAvia_Bot?start=beta_w1`

---

## 1. Код и репозиторий

- [ ] Убедиться, что работаете на ветке Phase A (не на `main` вслепую)
- [ ] Прогнать локально: `pytest tests/test_beta_phase_a.py -q`
- [ ] `push` ветки в origin
- [ ] Открыть PR → `main` (только после явного ОК)
- [ ] Review PR
- [ ] Merge в `main` (только после явного ОК)

---

## 2. Backup и подготовка VPS

- [ ] Свежий backup БД (`/var/backups/flyping/` или ваш скрипт)
- [ ] Проверить integrity backup
- [ ] Зафиксировать текущий SHA контейнера / образа (для rollback)
- [ ] Убедиться: один инстанс app (не масштабировать `beta_dispatcher` на несколько реплик)

---

## 3. Deploy

- [ ] Deploy новой версии на VPS (ваш обычный pipeline)
- [ ] Контейнер/сервис поднялся без restart-loop
- [ ] В логах нет ERROR на старте

---

## 4. Migration

- [ ] Применить `scripts/migrations/008_beta_flow.sql` к production DB  
  (идемпотентно: `CREATE TABLE/INDEX IF NOT EXISTS`)
- [ ] Повторный прогон миграции не падает и не портит данные
- [ ] Проверить наличие таблиц:  
  `beta_participants`, `beta_surveys`, `beta_bugs`, `beta_jobs`

**Важно:** `init_db()` beta-таблицы не создаёт. Без миграции `BETA_ENABLED=true` сломает flow.

---

## 5. Feature flags (после миграции)

В `.env` / secrets production:

- [ ] `BETA_ENABLED=true`
- [ ] `BETA_INVITE_CODES=w1`
- [ ] (опционально) `BETA_SURVEY_A_DELAY_SECONDS=90`
- [ ] (опционально) `BETA_DISPATCHER_INTERVAL_SECONDS=120`
- [ ] Перезапуск app, чтобы подтянуть env
- [ ] `ADMIN_TELEGRAM_USER_IDS` содержит только владельцев

Пока флаги выключены — поведение как до беты.

---

## 6. Smoke: инфраструктура

- [ ] `curl -fsS https://api.flyping.ru/api/ready` → `ready: true`, `issues: []`
- [ ] `curl -fsS https://api.flyping.ru/api/health` → ok, version актуальная, `demo_prices: false`
- [ ] Polling: бот отвечает на `/start` за несколько секунд
- [ ] Scheduler: в логах есть обычный price checker (без инцидента)
- [ ] В логах при старте: `Beta dispatcher interval=…` (если beta включена)

---

## 7. Smoke: Closed Beta flow

Владельцем / тестовым аккаунтом (не публиковать ссылку раньше времени):

- [ ] Открыть `https://t.me/FlyPingAvia_Bot?start=beta_w1`
- [ ] Видны блок «Закрытая бета» и кнопка «Понятно, участвую»
- [ ] Повторный `?start=beta_w1` не дублирует участника / onboarding
- [ ] Невалидный код (`?start=beta_nope`) → обычный старт без cohort
- [ ] Consent → создать подписку в Mini App
- [ ] Через ~90 с (+ интервал dispatcher) приходит Survey A
- [ ] Survey можно пройти; повторные тапы не плодят ответы
- [ ] `/bug` → тикет `BUG-N` (скриншот только как Telegram file_id, не на диск)
- [ ] `/beta_stop` отключает beta-сообщения (алерты цен остаются)
- [ ] `/cancel` или `/start` выводят из FSM `/bug` и Survey
- [ ] С обычного (не admin) аккаунта `/beta_status` молчит / недоступен
- [ ] С admin: `/beta_status` показывает participants / pending_jobs

---

## 8. Запуск волны

- [ ] Отправить приглашения (текст из Playbook §2.3) **только** со ссылкой `?start=beta_w1`
- [ ] Не слать сразу >8–12 людей (волна 1)

---

## 9. Наблюдение первые 30 минут

- [ ] Хвост логов app: нет всплеска ERROR / traceback по beta
- [ ] Нет пачек `telegram_forbidden` (если есть — ожидаемо при блокировке бота)
- [ ] `/beta_status`: pending_jobs не растёт бесконечно без consents
- [ ] Ready/health по-прежнему зелёные
- [ ] При P0: `/beta_pause` → стоп набора → разбор

---

## 10. Rollback (если нужно)

- [ ] `BETA_ENABLED=false` + restart (быстрый стоп beta-router и dispatcher)
- [ ] При необходимости — откат образа/SHA на предыдущий
- [ ] Таблицы `beta_*` можно оставить (данные участников); не дропать без нужды
- [ ] Сообщить тестировщикам коротко, что волна на паузе

---

## Готово

Когда пункты 1–7 зелёные — можно переходить к §8 (приглашения).
