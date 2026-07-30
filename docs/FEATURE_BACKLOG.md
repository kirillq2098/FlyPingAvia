# Feature Backlog — FlyPing

Связанные документы: [Strategy](FLYPING_STRATEGY.md) · [Roadmap](MASTER_ROADMAP.md) · [Competitive Analysis](COMPETITIVE_ANALYSIS.md) · [Vision](PRODUCT_VISION.md) · [Monetization](MONETIZATION.md) · [Architecture](TECH_ARCHITECTURE.md) · [Decisions](DECISIONS.md) · [KPI](KPI.md)

**Назначение:** единый реестр функций. Без обоснования из docs/кода фича сюда не попадает.  
**North Star:** Alerted Watchers (30d) — см. [FLYPING_STRATEGY](FLYPING_STRATEGY.md).  
**Оценки времени:** 1 разработчик, familiar с репо; ±50%.  
**Статусы:** `Done` · `Partial` · `Todo` · `Blocked` · `Icebox`

**Обоснование (колонка Source):** `Code` / `Strategy` / `Roadmap` / `Compete O#` / `Vision` / `Monetization` / `Decisions` / `Arch` / `Marketing`

---

## Легенда карточки

Каждая функция ниже в формате:

- **ID / Название**
- Описание · Проблема · Важность · Влияние на NSM · Value · Effort · Время · Приоритет · Зависимости · DoD · Метрики успеха · Статус · Source

**Score** в итоговой таблице = `Value / Effort` (выше — раньше в очереди при равном P).

---

# Реестр по разделам

## Core Search

### CS-01 · Поиск города словами + аэропорты города
- **Описание:** Резолв «Москва» → MOW + flightable airports; поиск cheapest across codes.
- **Проблема:** Пользователь не знает IATA.
- **Важность:** Без этого нет онбординга в RU.
- **NSM:** ↑ создание watches → больше шансов на алерт.
- **Value 9 · Effort 2 · Время:** done · **P0** (shipped)
- **Зависимости:** Travelpayouts cities/airports JSON
- **DoD:** resolve в боте и `/api/resolve`; alias’ы Москва/Питер
- **Метрики:** доля watches с `origin_name` заполненным
- **Статус:** Done · **Source:** Code, Vision

### CS-02 · Котировка + вилка дёшево/обычно/дорого
- **Описание:** Quote + P25/median/P75; пресеты порога.
- **Проблема:** Непонятно, какой порог ставить (Trip.com решает слайдером — Compete).
- **Важность:** Must-have Strategy §4.
- **NSM:** ↑ достижимые пороги → больше Alerted Watchers.
- **Value 9 · Effort 3 · Время:** done · **P0**
- **Зависимости:** CS-01, Travelpayouts token на проде
- **DoD:** вилка в боте и Mini App; пресеты дёшево/обычно
- **Метрики:** доля watches с порогом ≥ P25
- **Статус:** Done · **Source:** Code, Strategy, Compete O8

### CS-03 · One-way и round-trip в поиске/подписке
- **Описание:** FSM + Mini App trip type; RT ≈ сумма OW без live search (честный дисклеймер).
- **Проблема:** Нужны обе модели поездки.
- **Важность:** Базовый сценарий отпуска.
- **NSM:** ↑ coverage сценариев → больше watches.
- **Value 8 · Effort 4 · Время:** done · **P0**
- **Зависимости:** CS-02
- **DoD:** return_date в Watch; дисклеймер RT в UI
- **Метрики:** доля RT watches
- **Статус:** Done (Partial honesty на RT) · **Source:** Code, Decisions

### CS-04 · Партнёрская ссылка на билеты
- **Описание:** `build_affiliate_url` с marker в превью, карточках, алертах.
- **Проблема:** Нужен один шаг к покупке (USP).
- **Важность:** Единственная монетизация runtime.
- **NSM:** косвенно (алерт без ссылки бесполезен для бизнеса); leading → click.
- **Value 10 · Effort 2 · Время:** done · **P0**
- **Зависимости:** AFFILIATE_MARKER
- **DoD:** ссылка во всех алертах/карточках
- **Метрики:** брони в кабинете TP
- **Статус:** Done · **Source:** Code, Monetization, Strategy USP

### CS-05 · Предупреждение «порог ниже рынка»
- **Описание:** Если пользователь ставит порог ≪ P25 — явный trade-off «алертов почти не будет» (O8).
- **Проблема:** Мёртвые подписки убивают NSM.
- **Важность:** Must-have до роста (Strategy §4.10).
- **NSM:** **High** — прямо поднимает долю Alerted Watchers.
- **Value 8 · Effort 2 · Время:** 0.5–1 д · **P0**
- **Зависимости:** CS-02
- **DoD:** предупреждение в боте и Mini App при custom/threshold &lt; P25; можно всё равно сохранить
- **Метрики:** ↑ доля watches с ≥1 алертом за 30д
- **Статус:** Done · **Source:** Compete O8, Strategy

### CS-06 · UI пассажиров (взрослые/дети) + live quote
- **Описание:** Показать pax UI; цены через Flight Search API.
- **Проблема:** Семьи видят неверную «цену за состав» на кэше.
- **Важность:** Честность; сейчас сознательно скрыто.
- **NSM:** Medium — новые сегменты watches; риск врёных цен если включить рано.
- **Value 7 · Effort 7 · Время:** 5–10 д + доступ партнёра · **P2** / Blocked
- **Зависимости:** доступ Flight Search; TRAVELPAYOUTS_SEARCH_MARKER; LIVE_SEARCH_MODE
- **DoD:** UI включён; live quote для multi-pax; fallback с честным текстом
- **Метрики:** доля multi-pax watches; 403 rate = 0
- **Статус:** Blocked · **Source:** Decisions, Roadmap P1, Strategy non-goal until access

### CS-07 · Календарь дешевизны / гибкие даты (отдельный UX)
- **Описание:** Отдельный экран «дешёвые дни», не только «любая дата» в FSM.
- **Проблема:** Не знаю, когда лететь дешевле (есть у Skyscanner/Google).
- **Важность:** P2 README; не must-have USP watchdog.
- **NSM:** Low–Medium — больше watches с достижимыми датами.
- **Value 6 · Effort 7 · Время:** 7–14 д · **P2**
- **Зависимости:** CS-02; объём API calendar
- **DoD:** выбор даты из календаря цен в Mini App; сохранение watch
- **Метрики:** conversion search→watch для flexible users
- **Статус:** Partial · **Source:** Roadmap P2, Compete (Skyscanner/Google)
- **Partial note:** MVP окна дат `flexibility_days` ∈ {0,1,3,7} в боте/Mini App/checker (CS-07 MVP). Полный календарь дешевизны — Todo.

### CS-08 · Demo-режим только для разработки
- **Описание:** Политика: внешним пользователям всегда live token; demo не в проде.
- **Проблема:** Враньё ценами разрушает доверие.
- **Важность:** Strategy must-have §4.7.
- **NSM:** High (без реальных цен нет валидных алертов).
- **Value 9 · Effort 1 · Время:** 0.5 д (checks + docs) · **P0**
- **Зависимости:** ops/env
- **DoD:** `/api/health` demo_prices=false на проде; алерт в supervise при demo
- **Метрики:** demo_prices=false в health
- **Статус:** Partial (код есть; нужна ops-дисциплина) · **Source:** Strategy, Arch

---

## Tracking

### TR-01 · Создание / список / удаление подписок
- **Описание:** Watch CRUD в боте и Mini App; soft-delete.
- **Проблема:** Негде хранить «что сторожить».
- **Важность:** Ядро продукта.
- **NSM:** Foundation.
- **Value 10 · Effort 3 · Время:** done · **P0**
- **Зависимости:** DB
- **DoD:** add/list/unwatch; is_active=False
- **Метрики:** active watches / user
- **Статус:** Done · **Source:** Code, Vision

### TR-02 · Фоновая проверка цен (scheduler)
- **Описание:** APScheduler → PriceChecker по интервалу.
- **Проблема:** Нельзя вручную обновлять вкладку каждый день.
- **Важность:** Must-have.
- **NSM:** Foundation для алертов.
- **Value 10 · Effort 3 · Время:** done · **P0**
- **Зависимости:** CS-02, TR-01
- **DoD:** job `price_check`; обновление last_price/last_checked_at
- **Метрики:** % watches с last_checked_at &lt; 2×interval
- **Статус:** Done · **Source:** Code, Strategy

### TR-03 · Ручная проверка («Проверить сейчас»)
- **Описание:** `/check`, кнопки wcheck в карточках.
- **Проблема:** Недоверие к «проверим когда-нибудь» (слабость Google latency — O7).
- **Важность:** Честность оффера.
- **NSM:** Low–Medium (доверие → retention watches).
- **Value 7 · Effort 2 · Время:** done · **P0**
- **Зависимости:** TR-02
- **DoD:** ручной check обновляет карточки
- **Метрики:** частота ручных check
- **Статус:** Done · **Source:** Code, Compete O7

### TR-04 · Timestamp последней проверки в карточке
- **Описание:** Показывать `last_checked_at` явно в боте/Mini App/алерте.
- **Проблема:** Неясно, свежие ли данные.
- **Важность:** Strategy must-have §4.9.
- **NSM:** Medium (доверие → не удаляют watch).
- **Value 7 · Effort 2 · Время:** 0.5–1 д · **P0**
- **Зависимости:** TR-02 (поле уже есть)
- **DoD:** timestamp во всех карточках watches и в алерте
- **Метрики:** CSAT/интервью; ↓ удалений без алерта
- **Статус:** Partial (поле есть, UI не везде явный) · **Source:** Strategy, Compete O7

### TR-05 · Редактирование порога существующей подписки
- **Описание:** Сменить max_price без удаления watch.
- **Проблема:** После вилки/опыта порог хочется подкрутить.
- **Важность:** Снижает churn подписок.
- **NSM:** Medium — спасает «мёртвые» watches.
- **Value 7 · Effort 3 · Время:** 1–2 д · **P1**
- **Зависимости:** TR-01
- **DoD:** команда/кнопка/ Mini App edit; история last_alert сброс по правилам
- **Метрики:** % watches с edit; ↑ Alerted Watchers
- **Статус:** Todo · **Source:** Strategy (порог), UX gap vs Code

### TR-06 · Enforcement FREE_WATCH_LIMIT (или честный отказ)
- **Описание:** Либо применять лимит в handlers/API, либо убрать из README/конфига как «есть».
- **Проблема:** Документация врёт / freemium не готов.
- **Важность:** Roadmap P1; честность Decisions.
- **NSM:** Low сейчас; High позже для Premium.
- **Value 5 · Effort 3 · Время:** 1 д · **P1**
- **Зависимости:** решение в DECISIONS
- **DoD:** одно из двух: лимит работает с UX-сообщением **или** конфиг/доки очищены
- **Метрики:** hit-rate лимита (если включён)
- **Статус:** Todo · **Source:** Roadmap, Monetization, Decisions

---

## Notifications

### NT-01 · Алерт при price ≤ max_price + ссылка
- **Описание:** Checker шлёт HTML-карточку с CTA на билеты.
- **Проблема:** Нужно узнать о достижении порога.
- **Важность:** USP core.
- **NSM:** Direct driver.
- **Value 10 · Effort 3 · Время:** done · **P0**
- **Зависимости:** TR-02, CS-04
- **DoD:** алерт только при ≤ порога; есть affiliate URL
- **Метрики:** алерты / active watch
- **Статус:** Done · **Source:** Code, Strategy USP

### NT-02 · Явный контракт порога в тексте алерта
- **Описание:** «Цена X ≤ ваш порог Y», дельта (O1). Formatters частично есть — довести единообразие.
- **Проблема:** Размытые алерты конкурентов.
- **Важность:** Strategy / Compete P0.
- **NSM:** Medium — ↑ click / ↓ отписки.
- **Value 8 · Effort 2 · Время:** 0.5–1 д · **P0**
- **Зависимости:** NT-01
- **DoD:** все алерты содержат X, Y, сравнение; без двусмысленности
- **Метрики:** CTR (когда появится AN-01)
- **Статус:** Done · **Source:** Compete O1, Strategy

### NT-03 · Вилка рынка внутри алерта
- **Описание:** 🟢/🟡/🔴 + median в сообщении алерта (O3).
- **Проблема:** «Цена упала» без контекста.
- **Важность:** Отстройка от Aviasales bot / email-алертов.
- **NSM:** Medium — ↑ решение открыть билеты.
- **Value 8 · Effort 2 · Время:** 1 д · **P0**
- **Зависимости:** NT-01; band уже в checker path
- **DoD:** band в каждом алерте; fallback если band нет
- **Метрики:** CTR алертов
- **Статус:** Done · **Source:** Compete O3, Strategy

### NT-04 · Антиповтор / cooldown по last_alert_price
- **Описание:** Не слать повтор на ту же/почти ту же цену каждый цикл (O2).
- **Проблема:** Шум → удаление бота (слабость рынка digests).
- **Важность:** USP «молчит»; Strategy must-have §4.6; Roadmap P0.
- **NSM:** **High** — retention watches → больше шансов на будущий алерт.
- **Value 9 · Effort 3 · Время:** 1–2 д · **P0**
- **Зависимости:** NT-01; поле last_alert_price
- **DoD:** правило задокументировано в DECISIONS; тесты; нет дублей при стабильной цене
- **Метрики:** алерты на watch / неделя ↓ без потери Alerted Watchers
- **Статус:** Done · **Source:** Compete O2, Strategy, Roadmap, Decisions open

### NT-05 · Тихие часы
- **Описание:** Не беспокоить ночью; отложить алерт.
- **Проблема:** Push/бот ночью раздражает (KAYAK daily — паттерн шума).
- **Важность:** Secondary к NT-04; Strategy 10k stage.
- **NSM:** Medium retention.
- **Value 6 · Effort 4 · Время:** 2–3 д · **P2**
- **Зависимости:** NT-04; user pref (UA-02)
- **DoD:** настройка часов; отложенная доставка
- **Метрики:** % алертов в тихие часы = 0
- **Статус:** Todo · **Source:** Roadmap (тихие часы), Strategy 10k

---

## Telegram Experience

### TG-01 · FSM добавления подписки + меню команд
- **Описание:** /start, /add, /list, /help, reply keyboard, popular routes.
- **Проблема:** Нужен путь без Mini App.
- **Важность:** Telegram-first.
- **NSM:** Foundation onboarding.
- **Value 9 · Effort 4 · Время:** done · **P0**
- **Зависимости:** —
- **DoD:** полный happy-path в чате
- **Метрики:** /start → watch &lt; 24ч
- **Статус:** Done · **Source:** Code, Vision

### TG-02 · Позиционирование watchdog в /start (копирайт)
- **Описание:** «Не ищем 1000 рейсов — сторожим поездку» (O4); без BotFather-инструкций.
- **Проблема:** Путают с поисковиком Aviasales.
- **Важность:** Выбор vs конкурент в том же канале.
- **NSM:** Medium — ↑ conversion start→watch.
- **Value 7 · Effort 1 · Время:** 0.5 д · **P1**
- **Зависимости:** —
- **DoD:** A/B или зафиксированный текст в formatters; согласован со Strategy USP
- **Метрики:** start→watch rate
- **Статус:** Partial (тексты улучшались; USP-формулировка не зафиксирована) · **Source:** Compete O4, Strategy, Marketing

### TG-03 · Deep-link `?start=` с источником
- **Описание:** Парсинг payload; сохранить source на user (O6).
- **Проблема:** Нет атрибуции каналов/блогеров.
- **Важность:** Must-have к 1k (Strategy §4.11).
- **NSM:** High для роста качественного трафика.
- **Value 8 · Effort 4 · Время:** 2–3 д · **P1**
- **Зависимости:** UA-01 поле source; AN-02
- **DoD:** `t.me/bot?start=blogger_x` пишет source; отчёт по source
- **Метрики:** users by source; Alerted Watchers by source
- **Статус:** Todo · **Source:** Compete O6, Strategy, Marketing

### TG-04 · Шаринг карточки «жду цену ≤ N»
- **Описание:** Кнопка share + deep-link приглашения (O5).
- **Проблема:** Гиганты слабо шарятся; нужен organic.
- **Важность:** Strategy 1k growth.
- **NSM:** High (viral → new Alerted Watchers).
- **Value 8 · Effort 4 · Время:** 2–4 д · **P1**
- **Зависимости:** TG-03
- **DoD:** share из карточки watch; получатель проходит /start с payload
- **Метрики:** shares; invited→watch rate
- **Статус:** Todo · **Source:** Compete O5, Strategy, Marketing

### TG-05 · Не использовать MenuButtonWebApp с tunnel URL
- **Описание:** Уже решение: MenuButtonCommands; WebApp через кнопки.
- **Проблема:** Кэш URL → Error 1033.
- **Важность:** Reliability Mini App entry.
- **NSM:** Medium (иначе Mini App «мёртв»).
- **Value 8 · Effort 1 · Время:** done · **P0**
- **Зависимости:** —
- **DoD:** не ставить WebApp menu button на ephemeral URL
- **Метрики:** ошибки открытия Mini App
- **Статус:** Done · **Source:** Decisions, Code

---

## Web App

### WA-01 · Mini App поиск + подписки
- **Описание:** Вкладки Поиск / Подписки; quote; create watch; auth initData.
- **Проблема:** Формы в чате неудобны.
- **Важность:** Решённый UX Decisions.
- **NSM:** ↑ watches.
- **Value 9 · Effort 5 · Время:** done · **P0**
- **Зависимости:** WEBAPP_URL HTTPS
- **DoD:** полный flow в Telegram WebView
- **Метрики:** доля watches из Mini App vs бот
- **Статус:** Done · **Source:** Code, Decisions

### WA-02 · Стабильный публичный HTTPS / домен
- **Описание:** Named tunnel / VPS / домен вместо only trycloudflare; /setdomain.
- **Проблема:** Ephemeral URL ломает кнопку (Roadmap A, Strategy 100 users).
- **Важность:** P0 до внешнего трафика.
- **NSM:** **High** — без Mini App/кнопки падает onboarding.
- **Value 9 · Effort 5 · Время:** 2–5 д ops · **P0**
- **Зависимости:** Infra; деньги на VPS/домен
- **DoD:** постоянный URL в .env; health с публички 7д; BotFather domain
- **Метрики:** public health uptime
- **Статус:** Partial (supervise + quick tunnel) · **Source:** Roadmap, Strategy, Arch, Compete

### WA-03 · Состояние «Mini App недоступен» в боте
- **Описание:** Если WEBAPP_URL пуст/health fail — честный текст, полный FSM без давления на app.
- **Проблема:** Кнопка ведёт в никуда.
- **Важность:** Доверие на 100 users.
- **NSM:** Low–Medium.
- **Value 6 · Effort 2 · Время:** 0.5–1 д · **P1**
- **Зависимости:** WA-02 health
- **DoD:** нет битой кнопки; fallback на чат
- **Метрики:** ошибки open app
- **Статус:** Partial · **Source:** Strategy reliability

---

## User Account

### UA-01 · Профиль пользователя + source/attribution
- **Описание:** Расширить User: source, first_start_payload, created_at уже есть.
- **Проблема:** Нельзя считать каналы.
- **Важность:** Рост 1k.
- **NSM:** Enabling для TG-03/AN.
- **Value 6 · Effort 3 · Время:** 1–2 д · **P1**
- **Зависимости:** migration SQLite
- **DoD:** поля в DB; запись на /start
- **Метрики:** % users с source
- **Статус:** Todo · **Source:** Strategy, Marketing, Compete O6

### UA-02 · Настройки уведомлений (тихие часы)
- **Описание:** Prefs пользователя для NT-05.
- **Проблема:** Разный timezone/режим сна.
- **Важность:** С NT-05.
- **NSM:** Medium retention.
- **Value 5 · Effort 4 · Время:** 2–3 д · **P2**
- **Зависимости:** NT-05
- **DoD:** UI в боте; хранение prefs
- **Метрики:** % включивших тихие часы
- **Статус:** Todo · **Source:** Roadmap, Strategy 10k

---

## Premium

### PR-01 · Freemium-лимит маршрутов (продуктовая полка)
- **Описание:** После решения DECISIONS — лимит free + сообщение о premium.
- **Проблема:** Abuse / монетизация сверх CPA.
- **Важность:** Не раньше данных 1k (Strategy).
- **NSM:** Low напрямую; защищает unit economics.
- **Value 6 · Effort 5 · Время:** 3–5 д · **P2**
- **Зависимости:** TR-06 решение; желательно AN-01
- **DoD:** лимит + CTA; аналитика hit-rate
- **Метрики:** hit-rate; conversion to paid (если PR-02)
- **Статус:** Icebox until 1k data · **Source:** Monetization, Strategy 10k, Roadmap

### PR-02 · Платная подписка (Stars / карта)
- **Описание:** Оплата за лимиты/частоту/приоритет.
- **Проблема:** CPA может не покрыть рост.
- **Важность:** После unit-economics CPA.
- **NSM:** Low; lagging revenue.
- **Value 7 · Effort 9 · Время:** 15–30 д · **P2** / Future
- **Зависимости:** юрконтур; PR-01; платёжный провайдер
- **DoD:** оплата→флаг premium; биллинг; отмена
- **Метрики:** paid conversion; ARPU
- **Статус:** Icebox · **Source:** Monetization, Strategy non-early, Roadmap

### PR-03 · B2B / публичный API
- **Описание:** API для внешних клиентов.
- **Проблема:** чужой спрос (не validated).
- **Важность:** Explicitly after B2C (Strategy non-goal early).
- **NSM:** N/A B2C.
- **Value 4 · Effort 9 · Время:** 20+ д · **Icebox**
- **Зависимости:** стабильный B2C; SLA
- **DoD:** keys, docs, billing
- **Метрики:** B2B revenue
- **Статус:** Icebox · **Source:** Strategy §5, Roadmap E

---

## Analytics

### AN-01 · Трекинг alert → click (минимальный)
- **Описание:** Redirect/short-link или sub_id в marker + лог клика; сверка с TP.
- **Проблема:** Нет юнит-экономики (Roadmap B).
- **Важность:** Must-have до креаторов (Strategy §4.8).
- **NSM:** Enabling commercial KPI; косвенно качество алертов.
- **Value 8 · Effort 5 · Время:** 3–5 д · **P1**
- **Зависимости:** CS-04
- **DoD:** можно посчитать clicks / alerts за неделю
- **Метрики:** alert→click rate
- **Статус:** Todo · **Source:** Roadmap B, Strategy, KPI, Monetization

### AN-02 · KPI snapshot (SQL/скрипт)
- **Описание:** users, active watches, Alerted Watchers proxy, by source.
- **Проблема:** North Star не снимается регулярно.
- **Важность:** Управление продуктом.
- **NSM:** Direct measurement.
- **Value 7 · Effort 2 · Время:** 1 д · **P1**
- **Зависимости:** определение алерт-лога (таблица или парсинг)
- **DoD:** `scripts/kpi_snapshot` → markdown/stdout weekly
- **Метрики:** сам факт регулярного снятия
- **Статус:** Todo · **Source:** KPI TODO, Strategy

### AN-03 · Лог алертов в БД
- **Описание:** Таблица `alert_events` (watch_id, user_id, price, threshold, currency, sent_at); запись только после успешного `send_message`.
- **Проблема:** Сейчас Alerted Watchers плохо считать из last_alert_price alone.
- **Важность:** Точный North Star.
- **NSM:** **High** (измерение).
- **Value 8 · Effort 3 · Время:** 1–2 д · **P0**
- **Зависимости:** NT-01
- **DoD:** каждая успешная отправка пишется; запрос Alerted Watchers 30d (`scripts/kpi_alerted_watchers.sql`, `repo.count_alerted_watchers`)
- **Метрики:** Alerted Watchers считается SQL
- **Статус:** Done · **Source:** Strategy NSM, KPI
- **Артефакты:** `flypingavia/db/models.py` (`AlertEvent`), `repository.log_alert_event`, `checker.py`, `scripts/migrations/001_alert_events.sql`, `tests/test_alert_events.py`

---

## Growth

### GR-01 · Sub-marker по источнику в affiliate URL
- **Описание:** Разный marker/sub_id для blogger (O6 + Monetization TODO).
- **Проблема:** Один marker на всех — нельзя платить/оценивать каналы.
- **Важность:** 1k creators.
- **NSM:** High quality growth.
- **Value 8 · Effort 4 · Время:** 2–3 д · **P1**
- **Зависимости:** TG-03, UA-01
- **DoD:** URL зависит от user.source; дока для блогера
- **Метрики:** revenue by source в TP
- **Статус:** Todo · **Source:** Compete O6, Monetization, Marketing

### GR-02 · Блогер-кит (тексты/креативы, не код)
- **Описание:** 3 хука + ссылка deep-link; без «инструкции BotFather».
- **Проблема:** Нечего отдавать каналам (Marketing gap).
- **Важность:** Growth stage.
- **NSM:** Medium–High.
- **Value 7 · Effort 2 · Время:** 1–2 д контент · **P1**
- **Зависимости:** TG-03, WA-02
- **DoD:** файл в docs/ или Notion; 3 креатива согласованы со Strategy
- **Метрики:** creators onboarded; users from kit links
- **Статус:** Todo · **Source:** Marketing TODO, Strategy 1k

### GR-03 · SEO-минисайт
- **Описание:** Лендинг вне Telegram.
- **Проблема:** Нет discovery вне TG.
- **Важность:** Strategy — только после насыщения TG-каналов.
- **NSM:** Low early.
- **Value 5 · Effort 7 · Время:** 10–20 д · **Icebox** / Future
- **Зависимости:** бренд; WA-02
- **DoD:** лендинг + CTA на бота; базовая SEO
- **Метрики:** organic visits→/start
- **Статус:** Icebox · **Source:** Strategy 10k, Roadmap P2, Marketing

---

## Reliability

### RL-01 · Supervise watchdog (бот + tunnel)
- **Описание:** scripts/supervise.sh автоперезапуск, обновление WEBAPP_URL.
- **Проблема:** Сервис падал вместе с tunnel.
- **Важность:** Ops must.
- **NSM:** High (без аптайма нет алертов).
- **Value 9 · Effort 4 · Время:** done · **P0**
- **Зависимости:** —
- **DoD:** автоподъём задокументирован; health loop
- **Метрики:** MTTR; restarts/day
- **Статус:** Done · **Source:** Code, Decisions, Arch

### RL-02 · Выровнять версии (__init__ / pyproject / README)
- **Описание:** Единый 0.2.0 (или tag).
- **Проблема:** Рассинхрон статуса.
- **Важность:** Roadmap P0 мелкий.
- **NSM:** None прямо.
- **Value 3 · Effort 1 · Время:** 0.5 ч · **P0**
- **Зависимости:** —
- **DoD:** все версии совпадают; CHANGELOG
- **Метрики:** —
- **Статус:** Todo · **Source:** Roadmap, Decisions open, Arch

### RL-03 · Health-алерты админу при падении
- **Описание:** Если public/local health fail N раз — сообщение владельцу в Telegram.
- **Проблема:** Supervise чинит, но человек не знает о деградации DNS/API.
- **Важность:** До 100 внешних users.
- **NSM:** Medium (uptime).
- **Value 7 · Effort 3 · Время:** 1–2 д · **P1**
- **Зависимости:** RL-01; ADMIN_CHAT_ID
- **DoD:** алерт админу; без спама (cooldown)
- **Метрики:** время до обнаружения инцидента
- **Статус:** Todo · **Source:** Strategy risks, Arch

---

## Infrastructure

### IN-01 · Docker-образ
- **Описание:** Dockerfile + run с volume data.
- **Проблема:** Воспроизводимый деплой.
- **Важность:** Средняя до VPS.
- **NSM:** Enabling WA-02.
- **Value 6 · Effort 2 · Время:** done · **P1**
- **Зависимости:** —
- **DoD:** documented docker run
- **Метрики:** —
- **Статус:** Done · **Source:** Arch, Code

### IN-02 · Postgres + отдельный worker checker
- **Описание:** Масштаб БД и изоляция polling.
- **Проблема:** SQLite/один процесс упрётся на 10k (гипотеза Strategy).
- **Важность:** Не раньше нагрузки.
- **NSM:** Enabling at scale.
- **Value 6 · Effort 8 · Время:** 10–20 д · **P2** / Future
- **Зависимости:** метрики нагрузки
- **DoD:** Postgres URL; worker отдельным процессом; миграции
- **Метрики:** p95 check latency; DB locks
- **Статус:** Icebox until metrics · **Source:** Strategy 10k, Roadmap E, Arch TODO

### IN-03 · Секреты вне plaintext .env на сервере
- **Описание:** Нормальная secret management.
- **Проблема:** Риск утечки токенов.
- **Важность:** Растёт с командой/хостингом.
- **NSM:** None.
- **Value 5 · Effort 5 · Время:** 2–5 д · **P2**
- **Зависимости:** выбор хоста
- **DoD:** токены не в git; ротация описана
- **Метрики:** —
- **Статус:** Todo · **Source:** Arch TODO

---

## Internal Tools

### IT-01 · Документация продукта (docs/)
- **Описание:** Vision, Strategy, Compete, Backlog…
- **Проблема:** Решения теряются.
- **Важность:** Критерии разработки Strategy §12.
- **NSM:** Enabling focus.
- **Value 8 · Effort 3 · Время:** done (living) · **P0**
- **Зависимости:** —
- **DoD:** docs/README актуален
- **Метрики:** —
- **Статус:** Done · **Source:** Process

### IT-02 · Фикстуры/тесты на антиспам и alert log
- **Описание:** pytest на NT-04, AN-03.
- **Проблема:** Регрессии в деньгах внимания.
- **Важность:** С P0 notifications.
- **NSM:** Quality.
- **Value 6 · Effort 3 · Время:** 1–2 д · **P0**
- **Зависимости:** NT-04, AN-03
- **DoD:** тесты в CI локально pytest -q
- **Метрики:** coverage критичных веток
- **Статус:** Todo · **Source:** Arch tests gap, Strategy

---

## Explicit non-goals (в реестре как Icebox / Won’t)

| ID | Название | Почему в Icebox | Source |
|----|----------|-----------------|--------|
| NG-01 | Native iOS/Android | Нет преимущества vs Telegram до unit-economics | Strategy §5, Compete O9 |
| NG-02 | Свой booking / касса | Другой бизнес | Strategy §5 |
| NG-03 | Price Freeze / fintech | Капитал, регуляторика | Compete O10, Strategy |
| NG-04 | Virtual interlining | Риск доверия Kiwi | Compete O10, Strategy |
| NG-05 | Полный metasearch «как Aviasales» | Конфликт с партнёром/фокусом | Strategy USP |
| NG-06 | Отели/страховки как ядро | Размывает watchdog | Strategy §5 |
| NG-07 | Mistake-fare sniping / ultra-low latency | Невыполнимо честно | Strategy §5, Compete Google gaps |

---

# Release Plan

## MVP (0.2.x — сейчас / до внешнего трафика)

**Цель:** честный watchdog для первых людей.

| ID | Статус |
|----|--------|
| CS-01..04, CS-08 | Done / Partial ops |
| TR-01..03 | Done |
| NT-01 | Done |
| TG-01, TG-05 | Done |
| WA-01, RL-01, IN-01, IT-01 | Done |
| **TR-04, WA-02, RL-02, IT-02** | **Todo / Partial — закрыть до «зовём 100»** |
| AN-03, NT-04, NT-02, NT-03, CS-05 | Done |

## v1.0 — «Стабильный сторож»

**Цель:** Strategy этап 100→ начало 1k; NSM измерим; антиспам; стабильный URL.

- NT-04, NT-02, NT-03, CS-05, TR-04, AN-03, AN-02  
- WA-02, WA-03, RL-02, RL-03  
- TG-02  
- TR-06 (решение лимита)  
- Definition v1.0 = must-haves Strategy §4.1–4.10 + измеримый Alerted Watchers

## v1.1 — «Рост в Telegram»

**Цель:** 1k users, атрибуция, шаринг.

- TG-03, TG-04, UA-01, GR-01, GR-02, AN-01  
- TR-05  

## v2.0 — «Экономика и полки»

**Цель:** 10k; рычаги монетизации после данных.

- PR-01 (± PR-02 если данные за)  
- NT-05, UA-02  
- CS-06 **только если** Flight Search access  
- IN-02 при доказанной нагрузке  
- CS-07 если flexible — топ-запрос из интервью  

## Future / Icebox

- PR-03, GR-03, NG-01..07, CS-06 без доступа API  
- Всё из non-goals  

---

# Quick Wins

Критерии: Effort ≤ 3, Value ≥ 7, помогает NSM или росту, опирается на docs.

| ID | Почему quick win | Effort | Value | Score |
|----|------------------|--------|-------|-------|
| CS-05 | Предупреждение порога &lt; P25 — почти копирайт+if | 2 | 8 | 4.0 |
| NT-02 | Дожать текст контракта в алерте | 2 | 8 | 4.0 |
| NT-03 | Band уже есть в pipeline | 2 | 8 | 4.0 |
| TR-04 | Поле last_checked_at уже в модели | 2 | 7 | 3.5 |
| RL-02 | Строка версии | 1 | 3 | 3.0* |
| TG-02 | Копирайт /start под USP | 1 | 7 | 7.0 |
| AN-03 | Простая таблица событий | 3 | 8 | 2.7 |
| NT-04 | Логика на существующем поле | 3 | 9 | 3.0 |
| GR-02 | Контент без бэкенда | 2 | 7 | 3.5 |
| AN-02 | SQL-скрипт | 2 | 7 | 3.5 |

\*RL-02 низкий Value, но минутная работа — сделать пакетом с релизными правками.

**Рекомендуемый пакет «48 часов»:** NT-04 + NT-02 + NT-03 + CS-05 + TR-04 + RL-02.

---

# Expensive Features

| ID | Effort | Почему дорого / рискованно | Почему отложить |
|----|--------|----------------------------|-----------------|
| CS-06 | 7+ | Нужен доступ партнёра; иначе вратьё | Decisions: UI скрыт |
| CS-07 | 7 | Большой UI + API calendar; не USP | После интервью на 100–1k |
| PR-02 | 9 | Платежи, юр, поддержка | Strategy: после CPA economics |
| PR-03 | 9 | SLA чужих клиентов | После стабильного B2C |
| IN-02 | 8 | Миграции, ops | Нет метрик упирания SQLite |
| GR-03 | 7 | Контент+SEO без доказанного спроса вне TG | Strategy 10k |
| NG-03/04 | 10 | Капитал/поддержка | Explicit non-goals |
| NG-01 | 10 | Два стора, релизы | Telegram-first |

---

# Impact vs Effort

Оси: **Value (1–10)** × **Effort (1–10)**.  
Сортировка очереди разработки: сначала **P0**, внутри по **Score = Value/Effort** ↓; затем P1, P2; Icebox отдельно.

Только **не-Done** и не NG (для планирования работы). Done — внизу для полноты реестра.

| Очередь | ID | Раздел | P | Value | Effort | Score | Время | Статус |
|---------|----|--------|---|-------|--------|-------|-------|--------|
| 1 | TG-02 | Telegram | P1* | 7 | 1 | 7.0 | 0.5д | Partial |
| 2 | CS-05 | Search | P0 | 8 | 2 | 4.0 | 0.5–1д | Done |
| 3 | NT-02 | Notifications | P0 | 8 | 2 | 4.0 | 0.5–1д | Done |
| 4 | NT-03 | Notifications | P0 | 8 | 2 | 4.0 | 1д | Done |
| 5 | TR-04 | Tracking | P0 | 7 | 2 | 3.5 | 0.5–1д | Partial |
| 6 | GR-02 | Growth | P1 | 7 | 2 | 3.5 | 1–2д | Todo |
| 7 | AN-02 | Analytics | P1 | 7 | 2 | 3.5 | 1д | Todo |
| 8 | NT-04 | Notifications | P0 | 9 | 3 | 3.0 | 1–2д | Done |
| 9 | AN-03 | Analytics | P0 | 8 | 3 | 2.7 | 1–2д | Done |
| 10 | WA-03 | Web App | P1 | 6 | 2 | 3.0 | 0.5–1д | Partial |
| 11 | RL-02 | Reliability | P0 | 3 | 1 | 3.0 | 0.5ч | Todo |
| 12 | CS-08 | Search | P0 | 9 | 1 | 9.0 | 0.5д ops | Partial |
| 13 | RL-03 | Reliability | P1 | 7 | 3 | 2.3 | 1–2д | Todo |
| 14 | TR-05 | Tracking | P1 | 7 | 3 | 2.3 | 1–2д | Todo |
| 15 | TR-06 | Tracking | P1 | 5 | 3 | 1.7 | 1д | Todo |
| 16 | UA-01 | Account | P1 | 6 | 3 | 2.0 | 1–2д | Todo |
| 17 | TG-03 | Telegram | P1 | 8 | 4 | 2.0 | 2–3д | Todo |
| 18 | GR-01 | Growth | P1 | 8 | 4 | 2.0 | 2–3д | Todo |
| 19 | TG-04 | Telegram | P1 | 8 | 4 | 2.0 | 2–4д | Todo |
| 20 | WA-02 | Web App | P0 | 9 | 5 | 1.8 | 2–5д | Partial |
| 21 | AN-01 | Analytics | P1 | 8 | 5 | 1.6 | 3–5д | Todo |
| 22 | IT-02 | Internal | P0 | 6 | 3 | 2.0 | 1–2д | Todo |
| 23 | NT-05 | Notifications | P2 | 6 | 4 | 1.5 | 2–3д | Todo |
| 24 | UA-02 | Account | P2 | 5 | 4 | 1.3 | 2–3д | Todo |
| 25 | PR-01 | Premium | P2 | 6 | 5 | 1.2 | 3–5д | Icebox |
| 26 | IN-03 | Infra | P2 | 5 | 5 | 1.0 | 2–5д | Todo |
| 27 | CS-07 | Search | P2 | 6 | 7 | 0.9 | 7–14д | Partial |
| 28 | CS-06 | Search | P2 | 7 | 7 | 1.0 | 5–10д | Blocked |
| 29 | IN-02 | Infra | P2 | 6 | 8 | 0.8 | 10–20д | Icebox |
| 30 | GR-03 | Growth | Icebox | 5 | 7 | 0.7 | 10–20д | Icebox |
| 31 | PR-02 | Premium | Icebox | 7 | 9 | 0.8 | 15–30д | Icebox |
| 32 | PR-03 | Premium | Icebox | 4 | 9 | 0.4 | 20+д | Icebox |

\*TG-02 формально P1, но Score максимальный — делать в том же спринте, что P0-пакет.

### Уже сделано (не в очереди)

CS-01, CS-02, CS-03, CS-04, TR-01, TR-02, TR-03, NT-01, TG-01, TG-05, WA-01, RL-01, IN-01, IT-01, AN-03, NT-04, NT-02, NT-03, CS-05 — **Done**.

### Матрица (схема)

```text
Value ↑
10 | NT-01*  CS-04*     WA-02
 9 | NT-04   CS-05 CS-08     TG-01*
 8 | NT-02/03 AN-03 TG-03/04 GR-01 AN-01
 7 | TR-04 TG-02 TR-05 RL-03 GR-02     CS-06 PR-02
 6 | WA-03 PR-01 CS-07 IN-02
 5 | TR-06 UA-02 IN-03 GR-03
 4 | PR-03
 3 | RL-02
   +------------------------------------------------→ Effort
     1    2    3    4    5    6    7    8    9
* = Done
```

**Зона Quick Wins:** Value ≥7, Effort ≤3 (левый верх).  
**Зона Expensive defer:** Effort ≥7 без блокера роста NSM (правый низ/середина).

---

## Правила обновления backlog

1. Новая функция → карточка + Source + строка в Impact-таблице.  
2. Смена приоритета → ссылка на Strategy §12 / DECISIONS.  
3. Non-goal не переносится в Todo без записи в DECISIONS.  
4. После релиза — Статус `Done`, Release Plan обновить, CHANGELOG.

**Ближайший рекомендованный порядок (исполнение):**  
`CS-08 ops` → `NT-04` → `NT-02` → `NT-03` → `CS-05` → `TR-04` → `AN-03` → `WA-02` → `RL-02` → `TG-02` → далее v1.1 рост (TG-03…).
