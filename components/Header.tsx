"use client";

import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Logo } from "@/components/ui/Logo";
import { siteConfig } from "@/lib/site";
import { cn } from "@/lib/cn";

const NAV_LINKS = [
  { href: "#how-it-works", label: "Как работает" },
  { href: "#features", label: "Преимущества" },
  { href: "#comparison", label: "Сравнение" },
  { href: "#faq", label: "FAQ" },
] as const;

export function Header() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
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
    <header className="sticky top-0 z-50 px-3 pt-3 sm:px-4">
      <Container
        className={cn(
          "flex h-14 items-center justify-between rounded-[22px] px-4 transition-all duration-500 sm:h-16 sm:px-5",
          scrolled || open
            ? "glass-strong shadow-[0_16px_40px_rgba(15,23,42,0.08)]"
            : "border border-transparent bg-transparent",
        )}
      >
        <a
          href="#top"
          className="relative z-10 transition-transform duration-300 hover:scale-[1.02]"
          aria-label="FlyPing — наверх"
        >
          <Logo />
        </a>

        <nav
          className="hidden items-center gap-1 rounded-[18px] border border-slate-200/70 bg-white/55 p-1 shadow-[0_8px_24px_rgba(15,23,42,0.04)] backdrop-blur-xl md:flex"
          aria-label="Основная навигация"
        >
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-[14px] px-3.5 py-2 text-sm font-medium text-slate-600 transition-all duration-300 hover:bg-white hover:text-ink hover:shadow-[0_6px_16px_rgba(15,23,42,0.06)]"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden md:block">
          <Button href={siteConfig.telegramBotUrl} target="_blank" rel="noopener noreferrer">
            Открыть бота
          </Button>
        </div>

        <button
          type="button"
          className="relative z-10 inline-flex h-10 w-10 items-center justify-center rounded-[14px] text-ink ring-1 ring-slate-200/80 transition hover:bg-white md:hidden"
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? "Закрыть меню" : "Открыть меню"}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </Container>

      <AnimatePresence>
        {open ? (
          <motion.div
            id="mobile-menu"
            initial={{ opacity: 0, y: -10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="mx-auto mt-2 max-w-6xl overflow-hidden rounded-[22px] border border-slate-200/80 bg-white/90 shadow-[0_20px_50px_rgba(15,23,42,0.1)] backdrop-blur-xl md:hidden"
          >
            <div className="flex flex-col gap-1 p-3">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className="rounded-[16px] px-4 py-3 text-base font-medium text-ink transition hover:bg-brand-50/70"
                >
                  {link.label}
                </a>
              ))}
              <Button
                href={siteConfig.telegramBotUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 w-full"
                onClick={() => setOpen(false)}
              >
                Открыть Telegram-бота
              </Button>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  );
}
