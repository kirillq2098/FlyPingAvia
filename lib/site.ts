export const siteConfig = {
  name: "FlyPing",
  tagline: "Находите дешёвые авиабилеты первыми.",
  description:
    "FlyPing автоматически отслеживает стоимость авиабилетов и моментально сообщает о снижении цены через Telegram.",
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
