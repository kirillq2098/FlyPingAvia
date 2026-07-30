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
        <Logo />
        <div className="space-y-4 border border-line bg-bg-elevated p-6 sm:p-10">
          <h1 className="text-3xl font-semibold tracking-[-0.04em] text-ink">
            Политика конфиденциальности
          </h1>
          <p className="leading-7 text-mute">
            Документ будет дополнен перед публичным запуском. Сейчас {siteConfig.name}
            обрабатывает только данные, нужные для работы Telegram-бота и уведомлений
            о снижении цен.
          </p>
          <Link href="/" className="inline-flex text-sm font-medium text-blue hover:text-blue-deep">
            ← На главную
          </Link>
        </div>
      </Container>
    </main>
  );
}
