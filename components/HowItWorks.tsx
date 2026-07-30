"use client";

import { motion } from "framer-motion";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { HOW_IT_WORKS } from "@/lib/constants";

export function HowItWorks() {
  return (
    <section id="how-it-works" className="relative scroll-mt-24 py-20 sm:py-24">
      <Container>
        <Reveal>
          <SectionHeading
            eyebrow="Как это работает"
            title="Три шага до выгодного билета"
            description="Настройте маршрут один раз — дальше FlyPing следит за ценой и сообщает о снижении."
          />
        </Reveal>

        <div className="mt-14 grid gap-5 md:grid-cols-3">
          {HOW_IT_WORKS.map((item, index) => (
            <Reveal key={item.id} delay={index * 0.1}>
              <motion.article
                whileHover={{ y: -6, scale: 1.02 }}
                transition={{ type: "spring", stiffness: 320, damping: 22 }}
                className="group relative h-full overflow-hidden rounded-[24px] border border-slate-200/80 bg-white/90 p-6 shadow-[0_16px_40px_rgba(15,23,42,0.05)] backdrop-blur sm:p-7"
              >
                <div className="absolute -right-8 -top-8 h-28 w-28 rounded-full bg-gradient-to-br from-brand-400/15 to-sky-300/20 blur-2xl transition-opacity group-hover:opacity-100" />
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-[16px] bg-brand-50 text-sm font-bold text-brand-600 ring-1 ring-brand-100">
                  {item.step}
                </span>
                <h3 className="mt-5 text-xl font-semibold tracking-tight text-ink">
                  {item.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-600 sm:text-base">
                  {item.description}
                </p>
              </motion.article>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
