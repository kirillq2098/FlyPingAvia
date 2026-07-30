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
    <footer className="border-t border-line bg-surface py-12">
      <Container className="flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-sm space-y-3">
          <Logo />
          <p className="text-sm leading-6 text-muted">
            Мониторинг цен на авиабилеты и уведомления о снижении в Telegram.
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
                className="text-sm text-muted transition-colors hover:text-ink"
              >
                {link.label}
              </a>
            ) : (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm text-muted transition-colors hover:text-ink"
              >
                {link.label}
              </Link>
            ),
          )}
          <p className="pt-2 text-sm text-muted">
            © {year} {siteConfig.name}
          </p>
        </nav>
      </Container>
    </footer>
  );
}
