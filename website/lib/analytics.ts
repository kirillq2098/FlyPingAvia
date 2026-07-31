export const ANALYTICS_EVENTS = {
  telegramOpenHero: "telegram_open_hero",
  telegramOpenHeader: "telegram_open_header",
  telegramOpenFooter: "telegram_open_footer",
  telegramOpenCta: "telegram_open_cta",
  faqOpen: "faq_open",
  privacyOpen: "privacy_open",
  termsOpen: "terms_open",
} as const;

export type AnalyticsEvent =
  (typeof ANALYTICS_EVENTS)[keyof typeof ANALYTICS_EVENTS];

type AnalyticsPayload = Record<string, string | number | boolean | undefined>;

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
    ym?: (id: number, method: string, ...args: unknown[]) => void;
    dataLayer?: unknown[];
  }
}

export function trackEvent(
  event: AnalyticsEvent,
  payload: AnalyticsPayload = {},
): void {
  if (typeof window === "undefined") return;

  const gaId = process.env.NEXT_PUBLIC_GA_ID;
  const ymId = process.env.NEXT_PUBLIC_YANDEX_METRICA_ID;

  try {
    if (gaId && typeof window.gtag === "function") {
      window.gtag("event", event, payload);
    }

    if (ymId && typeof window.ym === "function") {
      const id = Number(ymId);
      if (!Number.isNaN(id)) {
        window.ym(id, "reachGoal", event, payload);
      }
    }

    if (process.env.NODE_ENV === "development") {
      console.info("[analytics]", event, payload);
    }
  } catch {
    // Analytics must never break UX.
  }
}
