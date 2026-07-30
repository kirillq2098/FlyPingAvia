"use client";

import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { SpotlightCard } from "@/components/ui/SpotlightCard";
import { FEATURES } from "@/lib/constants";

export function Features() {
  return (
    <section
      id="features"
      className="section-divider section-fade relative scroll-mt-24 py-20 sm:py-24"
    >
      <div className="pointer-events-none absolute inset-x-0 top-1/3 -z-10 mx-auto h-72 max-w-3xl rounded-full bg-brand-400/10 blur-3xl" />

      <Container>
        <Reveal>
          <SectionHeading
            eyebrow="Почему FlyPing"
            title="Всё, чтобы ловить низкие цены без усилий"
            description="Минимум действий с вашей стороны — максимум контроля над стоимостью перелёта."
          />
        </Reveal>

        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <Reveal key={feature.id} delay={index * 0.05}>
                <SpotlightCard className="h-full p-6">
                  <span className="inline-flex h-12 w-12 items-center justify-center rounded-[16px] bg-gradient-to-br from-brand-500 to-sky-400 text-white shadow-[0_12px_28px_rgba(37,99,235,0.3)] transition-transform duration-300 group-hover:scale-105 group-hover:rotate-3">
                    <Icon className="h-5 w-5" strokeWidth={2.2} />
                  </span>
                  <h3 className="mt-5 text-lg font-semibold tracking-[-0.02em] text-ink">
                    {feature.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">
                    {feature.description}
                  </p>
                </SpotlightCard>
              </Reveal>
            );
          })}
        </div>
      </Container>
    </section>
  );
}
