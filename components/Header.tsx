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
  { href: "#features", label: "Почему удобнее" },
  { href: "#gallery", label: "Пример" },
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
    <header
      className={cn(
        "sticky top-0 z-50 border-b transition-colors duration-300",
        scrolled || open
          ? "border-line bg-background/95 backdrop-blur-md"
          : "border-transparent bg-background/80",
      )}
    >
      <Container className="flex h-16 items-center justify-between">
        <a href="#top" aria-label="FlyPing — наверх">
          <Logo />
        </a>

        <nav className="hidden items-center gap-7 md:flex" aria-label="Основная навигация">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm text-muted transition-colors hover:text-ink"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden md:block">
          <Button href={siteConfig.telegramBotUrl} target="_blank" rel="noopener noreferrer">
            Запустить в Telegram
          </Button>
        </div>

        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-[var(--radius)] text-ink ring-1 ring-line md:hidden"
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
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="border-t border-line bg-background md:hidden"
          >
            <Container className="flex flex-col gap-1 py-3">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className="rounded-[var(--radius)] px-3 py-3 text-base text-ink hover:bg-surface"
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
                Запустить в Telegram
              </Button>
            </Container>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  );
}
