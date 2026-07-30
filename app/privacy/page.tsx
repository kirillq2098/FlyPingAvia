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
        <div className="space-y-4 rounded-[24px] border border-slate-200/80 bg-white/90 p-6 shadow-[0_16px_40px_rgba(15,23,42,0.05)] sm:p-10">
          <h1 className="text-3xl font-semibold tracking-tight text-ink">
            Политика конфиденциальности
          </h1>
          <p className="text-slate-600 leading-relaxed">
            Этот документ будет дополнен перед публичным запуском. Сейчас{" "}
            {siteConfig.name} обрабатывает только данные, необходимые для работы
            Telegram-бота и отправки уведомлений о снижении цен на авиабилеты.
          </p>
          <p className="text-slate-600 leading-relaxed">
            Если у вас есть вопросы по обработке данных, напишите нам через
            Telegram:{" "}
            <a
              href={siteConfig.telegramBotUrl}
              className="font-medium text-brand-600 hover:text-brand-500"
              target="_blank"
              rel="noopener noreferrer"
            >
              {siteConfig.telegramHandle}
            </a>
            .
          </p>
          <Link href="/" className="inline-flex text-sm font-semibold text-brand-600 hover:text-brand-500">
            ← Вернуться на главную
          </Link>
        </div>
      </Container>
    </main>
  );
}
