import type { Metadata } from "next";
import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Logo } from "@/components/ui/Logo";
import { siteConfig } from "@/lib/site";

export const metadata: Metadata = {
  title: "Пользовательское соглашение",
  description: `Пользовательское соглашение сервиса ${siteConfig.name}.`,
};

export default function TermsPage() {
  return (
    <main className="min-h-screen py-12 sm:py-16">
      <Container className="max-w-3xl space-y-8">
        <Logo />
        <div className="space-y-4 border border-line bg-bg-elevated p-6 sm:p-10">
          <h1 className="text-3xl font-semibold tracking-[-0.04em] text-ink">
            Пользовательское соглашение
          </h1>
          <p className="leading-7 text-mute">
            Используя {siteConfig.name}, вы соглашаетесь с условиями мониторинга цен
            на авиабилеты и получения уведомлений через Telegram.
          </p>
          <Link href="/" className="inline-flex text-sm font-medium text-blue hover:text-blue-deep">
            ← На главную
          </Link>
        </div>
      </Container>
    </main>
  );
}
