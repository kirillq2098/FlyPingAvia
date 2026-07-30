import Link from "next/link";
import { cn } from "@/lib/cn";
import { siteConfig } from "@/lib/config";
import type { AnalyticsEvent } from "@/lib/analytics";
import { TelegramLinkClient } from "@/components/TelegramLinkClient";

type ButtonVariant = "primary" | "ghost" | "on-dark" | "link";
type ButtonSize = "md" | "lg";

type CommonProps = {
  children: React.ReactNode;
  className?: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
};

type ButtonAsButton = CommonProps &
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    href?: undefined;
    eventName?: undefined;
  };

type ButtonAsLink = CommonProps & {
  href: string;
  target?: string;
  rel?: string;
  onClick?: React.MouseEventHandler<HTMLAnchorElement>;
  eventName?: AnalyticsEvent;
};

type ButtonProps = ButtonAsButton | ButtonAsLink;

const variants: Record<ButtonVariant, string> = {
  primary: "bg-blue text-white hover:bg-blue-deep",
  ghost: "bg-transparent text-ink ring-1 ring-line hover:bg-bg-elevated",
  "on-dark": "bg-white text-navy hover:bg-[#eef2f7]",
  link: "bg-transparent text-ink underline-offset-4 hover:underline",
};

const sizes: Record<ButtonSize, string> = {
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-5 text-sm sm:h-[3.1rem] sm:px-6 sm:text-[0.95rem]",
};

function buttonClasses(
  variant: ButtonVariant,
  size: ButtonSize,
  className?: string,
): string {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-[6px] font-medium tracking-[-0.015em] transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
    variant !== "link" && sizes[size],
    variants[variant],
    className,
  );
}

export function Button(props: ButtonProps) {
  const { children, className, variant = "primary", size = "md" } = props;
  const classes = buttonClasses(variant, size, className);

  if ("href" in props && props.href) {
    const { href, target, rel, onClick, eventName } = props;
    const isExternal = /^https?:\/\//i.test(href);
    const isTelegram = href === siteConfig.telegramBotUrl || href.includes("telegram");

    if (isExternal) {
      if (eventName || isTelegram) {
        return (
          <TelegramLinkClient
            href={href}
            className={classes}
            target={target ?? "_blank"}
            rel={rel ?? "noopener noreferrer"}
            eventName={eventName}
            onClick={onClick}
          >
            {children}
          </TelegramLinkClient>
        );
      }

      return (
        <a
          href={href}
          target={target ?? "_blank"}
          rel={rel ?? "noopener noreferrer"}
          onClick={onClick}
          className={classes}
        >
          {children}
        </a>
      );
    }

    return (
      <Link href={href} target={target} rel={rel} onClick={onClick} className={classes}>
        {children}
      </Link>
    );
  }

  const { type = "button", ...rest } = props as ButtonAsButton;
  return (
    <button type={type} className={classes} {...rest}>
      {children}
    </button>
  );
}
