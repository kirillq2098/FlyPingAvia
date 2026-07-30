import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Logo } from "@/components/ui/Logo";
import { siteConfig } from "@/lib/site";

export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-line bg-bg py-12">
      <Container className="flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-sm space-y-3">
          <Logo />
          <p className="text-sm leading-6 text-mute">
            Мониторинг цен на авиабилеты и уведомления о снижении в Telegram.
          </p>
        </div>
        <nav aria-label="Ссылки в подвале" className="flex flex-col gap-3 sm:items-end">
          <a
            href={siteConfig.telegramBotUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-mute hover:text-ink"
          >
            Telegram
          </a>
          <Link href={siteConfig.links.privacy} className="text-sm text-mute hover:text-ink">
            Политика конфиденциальности
          </Link>
          <Link href={siteConfig.links.terms} className="text-sm text-mute hover:text-ink">
            Пользовательское соглашение
          </Link>
          <p className="mono pt-2 text-xs text-mute">
            © {year} {siteConfig.name}
          </p>
        </nav>
      </Container>
    </footer>
  );
}
