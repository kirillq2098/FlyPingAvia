import type { Metadata } from "next";
import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Logo } from "@/components/ui/Logo";
import { siteConfig } from "@/lib/config";

export const metadata: Metadata = {
  title: "Политика конфиденциальности",
  description: `Политика конфиденциальности сервиса ${siteConfig.name}.`,
  alternates: { canonical: siteConfig.links.privacy },
};

export default function PrivacyPage() {
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
              Политика конфиденциальности
            </h1>
            <p className="mono text-xs text-mute">
              Дата вступления в силу: {siteConfig.legalEffectiveDate}
            </p>
            <p className="text-sm text-mute">
              Оператор: {siteConfig.legalEntityName}
            </p>
          </header>

          <Section title="1. Общие положения">
            <p>
              Настоящая Политика описывает, как {siteConfig.name} обрабатывает
              персональные и технические данные пользователей Telegram-бота и
              сайта {siteConfig.url}.
            </p>
            <p>
              {siteConfig.name} является информационным сервисом мониторинга цен
              на авиабилеты. Сервис не продаёт авиабилеты и не является
              авиакомпанией.
            </p>
          </Section>

          <Section title="2. Какие данные могут обрабатываться">
            <ul className="list-disc space-y-2 pl-5">
              <li>Telegram ID;</li>
              <li>username в Telegram;</li>
              <li>имя пользователя;</li>
              <li>выбранные маршруты;</li>
              <li>даты поездки;</li>
              <li>настройки уведомлений;</li>
              <li>технические данные (например, время обращений к сервису);</li>
              <li>обращения в поддержку.</li>
            </ul>
          </Section>

          <Section title="3. Цели обработки">
            <ul className="list-disc space-y-2 pl-5">
              <li>работа сервиса мониторинга цен;</li>
              <li>отправка уведомлений в Telegram;</li>
              <li>сохранение маршрутов пользователя;</li>
              <li>техническая поддержка;</li>
              <li>улучшение качества продукта.</li>
            </ul>
          </Section>

          <Section title="4. Переход к покупке билетов">
            <p>
              {siteConfig.name} не оформляет покупку авиабилетов. Переход к
              покупке может выполняться на сторонний сайт партнёра или
              поставщика. Условия покупки и обработка платёжных данных
              регулируются правилами соответствующего стороннего сервиса.
            </p>
          </Section>

          <Section title="5. Хранение и защита">
            <p>
              Данные хранятся столько, сколько необходимо для предоставления
              сервиса и исполнения обязательств. Мы применяем разумные
              организационные и технические меры для защиты данных.
            </p>
          </Section>

          <Section title="6. Контакты">
            <p>
              По вопросам обработки данных:{" "}
              <a
                className="font-medium text-blue hover:text-blue-deep"
                href={`mailto:${siteConfig.supportEmail}`}
              >
                {siteConfig.supportEmail}
              </a>
            </p>
            <p className="mono text-xs text-mute">
              Telegram: @{siteConfig.telegramUsername}
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
