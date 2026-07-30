"use client";

import { motion } from "framer-motion";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FEATURES } from "@/lib/constants";

export function Features() {
  return (
    <section id="features" className="relative scroll-mt-24 py-20 sm:py-24">
      <div className="pointer-events-none absolute inset-x-0 top-1/3 -z-10 mx-auto h-64 max-w-3xl rounded-full bg-brand-400/10 blur-3xl" />

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
              <Reveal key={feature.id} delay={index * 0.06}>
                <motion.article
                  whileHover={{ y: -6, scale: 1.015 }}
                  transition={{ type: "spring", stiffness: 300, damping: 20 }}
                  className="group h-full rounded-[22px] border border-slate-200/80 bg-white/85 p-6 shadow-[0_14px_36px_rgba(15,23,42,0.045)] backdrop-blur transition-shadow duration-300 hover:shadow-[0_22px_50px_rgba(37,99,235,0.1)]"
                >
                  <span className="inline-flex h-12 w-12 items-center justify-center rounded-[16px] bg-gradient-to-br from-brand-500 to-sky-400 text-white shadow-[0_10px_24px_rgba(37,99,235,0.28)]">
                    <Icon className="h-5 w-5" strokeWidth={2.2} />
                  </span>
                  <h3 className="mt-5 text-lg font-semibold tracking-tight text-ink">
                    {feature.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">
                    {feature.description}
                  </p>
                </motion.article>
              </Reveal>
            );
          })}
        </div>
      </Container>
    </section>
  );
}
