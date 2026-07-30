"use client";

import Link from "next/link";
import { trackEvent, type AnalyticsEvent } from "@/lib/analytics";

type TrackedLinkProps = {
  href: string;
  eventName: AnalyticsEvent;
  children: React.ReactNode;
  className?: string;
};

export function TrackedLink({
  href,
  eventName,
  children,
  className,
}: TrackedLinkProps) {
  return (
    <Link
      href={href}
      className={className}
      onClick={() => trackEvent(eventName)}
    >
      {children}
    </Link>
  );
}
