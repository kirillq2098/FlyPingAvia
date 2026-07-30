/**
 * Единая конфигурация сайта FlyPing.
 *
 * Перед публикацией заполните переменные из `.env.example`.
 * Telegram URL можно переопределить через NEXT_PUBLIC_TELEGRAM_BOT_URL.
 *
 * Актуальная рабочая ссылка на бота (Web Telegram):
 * https://web.telegram.org/k/#@FlyPingAvia_Bot
 *
 * Если понадобится t.me-ссылка, сначала проверьте, что username
 * открывает именно вашего бота (не чужой аккаунт с похожим именем).
 */

const env = {
  siteUrl: process.env.NEXT_PUBLIC_SITE_URL,
  telegramBotUrl: process.env.NEXT_PUBLIC_TELEGRAM_BOT_URL,
  telegramUsername: process.env.NEXT_PUBLIC_TELEGRAM_USERNAME,
  supportEmail: process.env.NEXT_PUBLIC_SUPPORT_EMAIL,
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
  url: trimTrailingSlash(env.siteUrl || "https://flyping.app"),
  /**
   * Username бота без @.
   * Замените через NEXT_PUBLIC_TELEGRAM_USERNAME при необходимости.
   */
  telegramUsername: env.telegramUsername || "FlyPingAvia_Bot",
  /**
   * URL Telegram-бота.
   * По умолчанию — проверенная Web Telegram deep link.
   * Переопределение: NEXT_PUBLIC_TELEGRAM_BOT_URL
   * Placeholder при отсутствии бота: https://t.me/FLYPING_BOT_USERNAME
   */
  telegramBotUrl:
    env.telegramBotUrl || "https://web.telegram.org/k/#@FlyPingAvia_Bot",
  /** Placeholder: замените на рабочий email поддержки перед публикацией. */
  supportEmail: env.supportEmail || "support@flyping.app",
  /** Placeholder: юридическое имя владельца / организации. */
  legalEntityName: "[УКАЖИТЕ ЮРИДИЧЕСКОЕ ИМЯ ВЛАДЕЛЬЦА]",
  /** Placeholder: дата вступления юридических документов в силу. */
  legalEffectiveDate: "[УКАЖИТЕ ДАТУ]",
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
