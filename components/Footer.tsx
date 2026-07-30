import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Logo } from "@/components/ui/Logo";
import { siteConfig } from "@/lib/site";

const FOOTER_LINKS = [
  { href: siteConfig.telegramBotUrl, label: "Telegram", external: true },
  { href: siteConfig.links.privacy, label: "Политика конфиденциальности", external: false },
  { href: siteConfig.links.terms, label: "Пользовательское соглашение", external: false },
] as const;

export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-slate-200/80 bg-white/70 py-12 backdrop-blur">
      <Container className="flex flex-col gap-8 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-3">
          <Logo />
          <p className="max-w-sm text-sm text-slate-600">
            Автоматический мониторинг авиабилетов и уведомления о снижении цены в Telegram.
          </p>
        </div>

        <nav aria-label="Ссылки в подвале" className="flex flex-col gap-3 sm:items-end">
          {FOOTER_LINKS.map((link) =>
            link.external ? (
              <a
                key={link.href}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-slate-600 transition-colors hover:text-brand-600"
              >
                {link.label}
              </a>
            ) : (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm font-medium text-slate-600 transition-colors hover:text-brand-600"
              >
                {link.label}
              </Link>
            ),
          )}
          <p className="pt-2 text-sm text-slate-500">© {year} {siteConfig.name}</p>
        </nav>
      </Container>
    </footer>
  );
}
