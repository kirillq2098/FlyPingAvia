import type { Metadata } from "next";
import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Logo } from "@/components/ui/Logo";
import { siteConfig } from "@/lib/config";

export const metadata: Metadata = {
  title: "Пользовательское соглашение",
  description: `Пользовательское соглашение сервиса ${siteConfig.name}.`,
  alternates: { canonical: siteConfig.links.terms },
};

export default function TermsPage() {
  return (
    <main id="main" className="min-h-screen py-10 sm:py-14">
      <Container className="max-w-3xl space-y-8">
        <Logo />
        <article className="space-y-8 border border-line bg-bg-elevated p-6 sm:p-10">
          <header className="space-y-3 border-b border-line pb-6">
            <p className="mono text-[11px] uppercase tracking-[0.16em] text-mute">
              legal
            </p>
            <h1 className="text-3xl font-semibold tracking-[-0.04em] text-ink sm:text-4xl">
              Пользовательское соглашение
            </h1>
            <p className="mono text-xs text-mute">
              Дата вступления в силу: {siteConfig.legalEffectiveDate}
            </p>
            <p className="text-sm text-mute">
              Оператор: {siteConfig.legalEntityName}
            </p>
          </header>

          <Section title="1. Предмет соглашения">
            <p>
              {siteConfig.name} — информационный сервис мониторинга цен на
              авиабилеты с уведомлениями в Telegram.
            </p>
            <p>
              Используя сайт или бота {siteConfig.name}, вы соглашаетесь с
              условиями настоящего соглашения.
            </p>
          </Section>

          <Section title="2. Статус сервиса">
            <ul className="list-disc space-y-2 pl-5">
              <li>{siteConfig.name} не является авиакомпанией;</li>
              <li>{siteConfig.name} не является продавцом авиабилетов;</li>
              <li>
                сервис предоставляет информацию о изменении цены и уведомления;
              </li>
              <li>
                покупка билета осуществляется на стороне партнёра или поставщика.
              </li>
            </ul>
          </Section>

          <Section title="3. Цены и наличие билетов">
            <ul className="list-disc space-y-2 pl-5">
              <li>цены на авиабилеты могут изменяться;</li>
              <li>наличие билета по указанной цене не гарантируется;</li>
              <li>
                пользователь самостоятельно проверяет условия тарифа перед
                покупкой;
              </li>
              <li>
                {siteConfig.name} не отвечает за действия сторонних сайтов и
                поставщиков.
              </li>
            </ul>
          </Section>

          <Section title="4. Доступность сервиса">
            <p>
              Сервис может временно быть недоступен из‑за технических работ,
              сбоев или ограничений сторонних платформ, включая Telegram.
            </p>
          </Section>

          <Section title="5. Прекращение использования">
            <p>
              Пользователь может прекратить использование бота в любой момент:
              удалить маршруты, остановить уведомления или заблокировать бота в
              Telegram.
            </p>
          </Section>

          <Section title="6. Контакты">
            <p>
              Вопросы по соглашению:{" "}
              <a
                className="font-medium text-blue hover:text-blue-deep"
                href={`mailto:${siteConfig.supportEmail}`}
              >
                {siteConfig.supportEmail}
              </a>
            </p>
          </Section>

          <Link
            href="/"
            className="inline-flex text-sm font-medium text-blue hover:text-blue-deep"
          >
            ← На главную
          </Link>
        </article>
      </Container>
    </main>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-semibold tracking-[-0.03em] text-ink">{title}</h2>
      <div className="space-y-3 text-sm leading-7 text-mute sm:text-base">{children}</div>
    </section>
  );
}
