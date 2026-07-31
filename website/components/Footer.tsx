import { Container } from "@/components/ui/Container";
import { Logo } from "@/components/ui/Logo";
import { TelegramLinkClient } from "@/components/TelegramLinkClient";
import { TrackedLink } from "@/components/TrackedLink";
import { ANALYTICS_EVENTS } from "@/lib/analytics";
import { siteConfig } from "@/lib/config";

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
          <TelegramLinkClient
            href={siteConfig.telegramBotUrl}
            eventName={ANALYTICS_EVENTS.telegramOpenFooter}
            className="text-sm text-mute hover:text-ink"
          >
            Telegram
          </TelegramLinkClient>
          <TrackedLink
            href={siteConfig.links.privacy}
            eventName={ANALYTICS_EVENTS.privacyOpen}
            className="text-sm text-mute hover:text-ink"
          >
            Политика конфиденциальности
          </TrackedLink>
          <TrackedLink
            href={siteConfig.links.terms}
            eventName={ANALYTICS_EVENTS.termsOpen}
            className="text-sm text-mute hover:text-ink"
          >
            Пользовательское соглашение
          </TrackedLink>
          <p className="mono pt-2 text-xs text-mute">
            © {year} {siteConfig.name}
          </p>
        </nav>
      </Container>
    </footer>
  );
}
