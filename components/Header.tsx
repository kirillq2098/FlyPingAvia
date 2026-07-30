"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Logo } from "@/components/ui/Logo";
import { siteConfig } from "@/lib/config";
import { ANALYTICS_EVENTS } from "@/lib/analytics";
import { cn } from "@/lib/cn";

const NAV = [
  { href: "#flow", label: "Как работает" },
  { href: "#interface", label: "Возможности" },
  { href: "#faq", label: "Вопросы" },
] as const;

export function Header() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 6);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <header
      className={cn(
        "sticky top-0 z-50 border-b transition-colors",
        scrolled || open ? "border-line bg-bg/95 backdrop-blur-sm" : "border-transparent bg-bg",
      )}
    >
      <Container className="flex h-16 items-center justify-between gap-6">
        <Logo />
        <nav className="hidden items-center gap-8 md:flex" aria-label="Основная навигация">
          {NAV.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-sm text-mute transition-colors hover:text-ink"
            >
              {item.label}
            </a>
          ))}
        </nav>
        <div className="hidden md:block">
          <Button
            href={siteConfig.telegramBotUrl}
            target="_blank"
            rel="noopener noreferrer"
            eventName={ANALYTICS_EVENTS.telegramOpenHeader}
          >
            Открыть Telegram
          </Button>
        </div>
        <button
          type="button"
          className="mono inline-flex h-10 items-center rounded-[6px] px-3 text-xs uppercase tracking-[0.12em] text-ink ring-1 ring-line md:hidden"
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Close" : "Menu"}
        </button>
      </Container>

      <AnimatePresence>
        {open ? (
          <motion.div
            id="mobile-nav"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-line bg-bg md:hidden"
          >
            <Container className="flex flex-col gap-1 py-3">
              {NAV.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className="px-1 py-3 text-base text-ink"
                >
                  {item.label}
                </a>
              ))}
              <Button
                href={siteConfig.telegramBotUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 w-full"
                eventName={ANALYTICS_EVENTS.telegramOpenHeader}
                onClick={() => setOpen(false)}
              >
                Открыть Telegram
              </Button>
            </Container>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  );
}
