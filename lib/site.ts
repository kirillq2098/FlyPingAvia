export const siteConfig = {
  name: "FlyPing",
  tagline: "Билет подешевел. FlyPing уже сообщил.",
  description:
    "Укажите маршрут один раз. FlyPing будет следить за ценой и отправит сообщение в Telegram, когда появится более выгодный билет.",
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
