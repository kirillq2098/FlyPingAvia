"use client";

import { trackEvent, type AnalyticsEvent } from "@/lib/analytics";

type TelegramLinkClientProps = {
  href: string;
  children: React.ReactNode;
  className?: string;
  target?: string;
  rel?: string;
  eventName?: AnalyticsEvent;
  onClick?: React.MouseEventHandler<HTMLAnchorElement>;
};

/**
 * External CTA link with optional analytics.
 * Uses native <a> so Telegram Web hash URLs are preserved.
 */
export function TelegramLinkClient({
  href,
  children,
  className,
  target = "_blank",
  rel = "noopener noreferrer",
  eventName,
  onClick,
}: TelegramLinkClientProps) {
  return (
    <a
      href={href}
      target={target}
      rel={rel}
      className={className}
      onClick={(event) => {
        if (eventName) {
          trackEvent(eventName);
        }
        onClick?.(event);
      }}
    >
      {children}
    </a>
  );
}
