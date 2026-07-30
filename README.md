# FlyPing

Современный SaaS-лендинг для сервиса и Telegram-бота **FlyPing** — автоматический мониторинг цен на авиабилеты с мгновенными уведомлениями.

## Стек

- Next.js (App Router)
- TypeScript
- Tailwind CSS
- Framer Motion
- Lucide Icons

## Запуск

```bash
npm install
npm run dev
```

Откройте [http://localhost:3000](http://localhost:3000).

## Структура

```text
app/                 # маршруты, SEO, metadata, robots, sitemap
components/          # секции лендинга
components/ui/       # переиспользуемые UI-примитивы
lib/                 # конфиг сайта, контент, feature flags
types/               # доменные типы под будущие модули
public/              # статичные ассеты
```

## Будущие модули

Архитектура уже учитывает расширение без перестройки проекта:

- личный кабинет
- авторизация через Telegram
- платная подписка
- история уведомлений
- блог
- страница тарифов
- админ-панель

См. `lib/features.ts` и `types/index.ts`.
