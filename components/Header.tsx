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
    const onScroll = () => setScrolled(window.scrollY > 12);
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
        "sticky top-0 z-50 border-b border-transparent transition-all duration-300",
        scrolled &&
          "border-slate-200/70 bg-surface/80 shadow-[0_8px_30px_rgba(15,23,42,0.06)] backdrop-blur-xl",
      )}
    >
      <Container className="flex h-16 items-center justify-between md:h-[4.5rem]">
        <a href="#top" className="relative z-10" aria-label="FlyPing — наверх">
          <Logo />
        </a>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Основная навигация">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-slate-600 transition-colors hover:text-ink"
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
          className="relative z-10 inline-flex h-10 w-10 items-center justify-center rounded-[14px] text-ink ring-1 ring-slate-200/80 md:hidden"
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
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="border-t border-slate-200/70 bg-surface/95 backdrop-blur-xl md:hidden"
          >
            <Container className="flex flex-col gap-2 py-4">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className="rounded-[16px] px-4 py-3 text-base font-medium text-ink hover:bg-white"
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
            </Container>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  );
}
