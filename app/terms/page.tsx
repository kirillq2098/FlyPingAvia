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
        <Link href="/" className="inline-flex">
          <Logo />
        </Link>
        <div className="space-y-4 border border-line bg-surface-raised p-6 sm:p-10 rounded-[var(--radius-lg)]">
          <h1 className="display text-3xl text-ink">Пользовательское соглашение</h1>
          <p className="leading-7 text-muted">
            Используя {siteConfig.name}, вы соглашаетесь с условиями сервиса
            мониторинга цен на авиабилеты и получения уведомлений через Telegram.
          </p>
          <p className="leading-7 text-muted">
            Полная юридическая редакция будет опубликована до коммерческого
            запуска. Сервис предоставляется «как есть» и не гарантирует наличие
            билетов по указанной цене на момент покупки.
          </p>
          <Link href="/" className="inline-flex text-sm font-medium text-brand hover:text-brand-hover">
            ← На главную
          </Link>
        </div>
      </Container>
    </main>
  );
}
