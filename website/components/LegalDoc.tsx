import type { ReactNode } from "react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Container } from "@/components/ui/Container";
import { siteConfig } from "@/lib/config";

type LegalSection = {
  id: string;
  title: string;
  content: ReactNode;
};

type LegalDocProps = {
  title: string;
  description: string;
  sections: LegalSection[];
};

export function LegalDoc({ title, description, sections }: LegalDocProps) {
  return (
    <>
      <Header />
      <main id="main" className="bg-bg pb-20 pt-10 sm:pt-14">
        <Container className="max-w-3xl">
          <p className="mono text-[11px] uppercase tracking-[0.16em] text-mute">
            Legal · {siteConfig.name}
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-ink sm:text-4xl">
            {title}
          </h1>
          <p className="mt-3 text-sm leading-6 text-mute sm:text-base">{description}</p>
          <p className="mono mt-4 text-xs text-mute">
            Дата вступления в силу: {siteConfig.legalEffectiveDate}
          </p>

          <div className="mt-10 divide-y divide-line border-y border-line">
            {sections.map((section) => (
              <section key={section.id} id={section.id} className="py-7">
                <h2 className="text-lg font-semibold tracking-[-0.02em] text-ink">
                  {section.title}
                </h2>
                <div className="mt-3 space-y-3 text-sm leading-7 text-mute sm:text-[15px]">
                  {section.content}
                </div>
              </section>
            ))}
          </div>

          <p className="mt-8 text-sm leading-6 text-mute">
            Вопросы по этому документу:{" "}
            <a
              href={`mailto:${siteConfig.supportEmail}`}
              className="text-blue underline-offset-2 hover:underline"
            >
              {siteConfig.supportEmail}
            </a>
            {" · "}
            <a
              href={siteConfig.supportTelegramUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue underline-offset-2 hover:underline"
            >
              @{siteConfig.supportTelegramUsername}
            </a>
          </p>
        </Container>
      </main>
      <Footer />
    </>
  );
}
