"use client";

import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { SpotlightCard } from "@/components/ui/SpotlightCard";
import { HOW_IT_WORKS } from "@/lib/constants";

export function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="section-divider section-fade relative scroll-mt-24 py-20 sm:py-24"
    >
      <Container>
        <Reveal>
          <SectionHeading
            eyebrow="Как это работает"
            title="Три шага до выгодного билета"
            description="Настройте маршрут один раз — дальше FlyPing следит за ценой и сообщает о снижении."
          />
        </Reveal>

        <div className="relative mt-14 grid gap-5 md:grid-cols-3">
          <div className="pointer-events-none absolute left-[16%] right-[16%] top-[3.25rem] hidden h-px bg-gradient-to-r from-brand-200 via-sky-300 to-brand-200 md:block" />

          {HOW_IT_WORKS.map((item, index) => (
            <Reveal key={item.id} delay={index * 0.1}>
              <SpotlightCard className="h-full p-6 sm:p-7">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-[16px] bg-gradient-to-br from-brand-50 to-sky-50 text-sm font-bold text-brand-600 ring-1 ring-brand-100/80 shadow-[0_8px_20px_rgba(37,99,235,0.08)]">
                  {item.step}
                </span>
                <h3 className="mt-5 text-xl font-semibold tracking-[-0.02em] text-ink">
                  {item.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-600 sm:text-base">
                  {item.description}
                </p>
              </SpotlightCard>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
