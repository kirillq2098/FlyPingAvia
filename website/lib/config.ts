/**
 * Единая конфигурация сайта FlyPing.
 *
 * Перед публикацией при необходимости переопределите переменные из `.env.example`.
 *
 * Бот (продукт): Web Telegram → @FlyPingAvia_Bot
 * Поддержка: @Akulov_Kirill / Q2098@yandex.ru
 */

const env = {
  siteUrl: process.env.NEXT_PUBLIC_SITE_URL,
  telegramBotUrl: process.env.NEXT_PUBLIC_TELEGRAM_BOT_URL,
  telegramUsername: process.env.NEXT_PUBLIC_TELEGRAM_USERNAME,
  supportEmail: process.env.NEXT_PUBLIC_SUPPORT_EMAIL,
  supportTelegram: process.env.NEXT_PUBLIC_SUPPORT_TELEGRAM,
  gaId: process.env.NEXT_PUBLIC_GA_ID,
  yandexMetricaId: process.env.NEXT_PUBLIC_YANDEX_METRICA_ID,
};

function trimTrailingSlash(value: string): string {
  return value.replace(/\/$/, "");
}

export const siteConfig = {
  name: "FlyPing",
  tagline: "Билет подешевел. FlyPing уже сообщил.",
  description:
    "FlyPing следит за стоимостью выбранных авиабилетов и отправляет уведомление в Telegram, когда цена снижается.",
  seoTitle: "FlyPing — уведомления о снижении цен на авиабилеты",
  locale: "ru_RU",
  url: trimTrailingSlash(env.siteUrl || "https://flyping.ru"),
  /**
   * Username бота без @.
   * Переопределение: NEXT_PUBLIC_TELEGRAM_USERNAME
   */
  telegramUsername: env.telegramUsername || "FlyPingAvia_Bot",
  /**
   * URL Telegram-бота (продукт).
   * По умолчанию — native t.me deep-link с beta attribution (site1).
   * Переопределение: NEXT_PUBLIC_TELEGRAM_BOT_URL
   */
  telegramBotUrl:
    env.telegramBotUrl || "https://t.me/FlyPingAvia_Bot?start=beta_site1",
  /** Email для юридических уведомлений и поддержки. */
  supportEmail: env.supportEmail || "Q2098@yandex.ru",
  /** Telegram поддержки (не путать с ботом продукта). */
  supportTelegramUsername: "Akulov_Kirill",
  supportTelegramUrl:
    env.supportTelegram || "https://t.me/Akulov_Kirill",
  /** Оператор сервиса (физическое лицо). */
  legalEntityName: "Акулов Кирилл Анатольевич",
  legalEntityType: "физическое лицо",
  /** Дата вступления Политики и Соглашения в силу. */
  legalEffectiveDate: "11.08.2026",
  /** Хостинг и хранение данных. */
  hostingProvider: "VPS Timeweb (Российская Федерация)",
  /** Источник данных о ценах. */
  priceDataSource: "API Aviasales",
  links: {
    privacy: "/privacy",
    terms: "/terms",
    home: "/",
  },
  analytics: {
    gaId: env.gaId || "",
    yandexMetricaId: env.yandexMetricaId || "",
  },
} as const;

export type SiteConfig = typeof siteConfig;

/** @deprecated Используйте `siteConfig` из `@/lib/config`. */
export const config = siteConfig;
