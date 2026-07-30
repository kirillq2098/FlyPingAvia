export const siteConfig = {
  name: "FlyPing",
  tagline: "Цена на билет изменилась. Вы узнаете первым.",
  description:
    "FlyPing следит за выбранным маршрутом и присылает сообщение в Telegram, когда билет становится дешевле.",
  url: "https://flyping.app",
  locale: "ru_RU",
  telegramBotUrl: "https://t.me/FlyPingBot",
  telegramHandle: "@FlyPingBot",
  links: {
    privacy: "/privacy",
    terms: "/terms",
    blog: "/blog",
    pricing: "/pricing",
    dashboard: "/dashboard",
    admin: "/admin",
  },
} as const;

export type SiteConfig = typeof siteConfig;
