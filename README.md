# FlyPing

FlyPing — информационный сервис мониторинга цен на авиабилеты.  
Пользователь указывает маршрут в Telegram, а сервис отправляет уведомление, когда цена снижается.

Сайт — маркетинговый лендинг с утверждённым визуальным языком аэропортовой навигации.

## Стек

- Next.js (App Router)
- TypeScript
- Tailwind CSS
- Framer Motion

## Требования

- Node.js 20+
- npm 10+

## Установка

```bash
npm install
cp .env.example .env.local
```

## Запуск

```bash
npm run dev
```

Откройте [http://localhost:3000](http://localhost:3000).

## Production build

```bash
npm run lint
npm run typecheck
npm run build
npm start
```

## Переменные окружения

См. `.env.example`:

| Переменная | Назначение |
|---|---|
| `NEXT_PUBLIC_SITE_URL` | Канонический домен сайта |
| `NEXT_PUBLIC_TELEGRAM_BOT_URL` | Ссылка на Telegram-бота |
| `NEXT_PUBLIC_TELEGRAM_USERNAME` | Username бота без `@` |
| `NEXT_PUBLIC_SUPPORT_EMAIL` | Email поддержки |
| `NEXT_PUBLIC_GA_ID` | Google Analytics 4 Measurement ID |
| `NEXT_PUBLIC_YANDEX_METRICA_ID` | ID счётчика Яндекс Метрики |

Если `NEXT_PUBLIC_GA_ID` / `NEXT_PUBLIC_YANDEX_METRICA_ID` пустые, аналитика не подключается.

## Настройка Telegram-ссылки

Единый источник: `lib/config.ts`.

По умолчанию используется проверенная ссылка:

`https://web.telegram.org/k/#@FlyPingAvia_Bot`

Переопределение:

```bash
NEXT_PUBLIC_TELEGRAM_BOT_URL=https://web.telegram.org/k/#@FlyPingAvia_Bot
```

Все CTA берут URL из конфигурации и открываются в новой вкладке с `rel="noopener noreferrer"`.

## Аналитика

Компонент: `components/Analytics.tsx`  
События: `lib/analytics.ts`

События:

- `telegram_open_hero`
- `telegram_open_header`
- `telegram_open_footer`
- `telegram_open_cta`
- `faq_open`
- `privacy_open`
- `terms_open`

## Структура проекта

```text
app/                 # маршруты, SEO, legal, 404, manifest
components/          # секции лендинга и UI
lib/                 # config, analytics, constants
public/images/       # оптимизированные изображения
```

## Деплой на Vercel

1. Подключите репозиторий к Vercel.
2. Добавьте переменные окружения из `.env.example`.
3. Deploy — `npm run build` выполнится автоматически.
4. Проверьте `/`, `/privacy`, `/terms`, `/robots.txt`, `/sitemap.xml`.

## Юридические данные и env

В `lib/config.ts` уже заданы оператор, дата документов и контакты.
При деплое при необходимости переопределите через env:

- `NEXT_PUBLIC_SITE_URL` — боевой домен (`https://flyping.ru`);
- `NEXT_PUBLIC_SUPPORT_EMAIL` / `NEXT_PUBLIC_SUPPORT_TELEGRAM` — поддержка;
- `NEXT_PUBLIC_TELEGRAM_BOT_URL` — ссылка на бота продукта.

## Лицензия

Private.
