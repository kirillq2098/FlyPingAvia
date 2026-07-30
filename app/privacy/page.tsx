import type { Metadata } from "next";
import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Logo } from "@/components/ui/Logo";
import { siteConfig } from "@/lib/site";

export const metadata: Metadata = {
  title: "Политика конфиденциальности",
  description: `Политика конфиденциальности сервиса ${siteConfig.name}.`,
};

export default function PrivacyPage() {
  return (
    <main className="min-h-screen py-12 sm:py-16">
      <Container className="max-w-3xl space-y-8">
        <Link href="/" className="inline-flex">
          <Logo />
        </Link>
        <div className="space-y-4 border border-line bg-surface-raised p-6 sm:p-10 rounded-[var(--radius-lg)]">
          <h1 className="display text-3xl text-ink">Политика конфиденциальности</h1>
          <p className="leading-7 text-muted">
            Этот документ будет дополнен перед публичным запуском. Сейчас{" "}
            {siteConfig.name} обрабатывает только данные, необходимые для работы
            Telegram-бота и отправки уведомлений о снижении цен на авиабилеты.
          </p>
          <p className="leading-7 text-muted">
            Вопросы по данным:{" "}
            <a
              href={siteConfig.telegramBotUrl}
              className="font-medium text-brand hover:text-brand-hover"
              target="_blank"
              rel="noopener noreferrer"
            >
              {siteConfig.telegramHandle}
            </a>
            .
          </p>
          <Link href="/" className="inline-flex text-sm font-medium text-brand hover:text-brand-hover">
            ← На главную
          </Link>
        </div>
      </Container>
    </main>
  );
}
