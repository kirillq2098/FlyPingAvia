"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";

const STEPS = [
  { code: "01", title: "Маршрут задан", meta: "OVB → LED" },
  { code: "02", title: "Цена проверяется", meta: "каждые 30 мин" },
  { code: "03", title: "Цена снизилась", meta: "−4 320 ₽" },
  { code: "04", title: "Уведомление отправлено", meta: "Telegram" },
] as const;

export function ProductFlow() {
  const reduceMotion = useReducedMotion();

  return (
    <section id="flow" className="scroll-mt-24 border-y border-line py-16 sm:py-20">
      <Container>
        <Reveal>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <h2 className="max-w-xl text-3xl font-semibold tracking-[-0.04em] text-ink sm:text-4xl">
              Один маршрут. Непрерывный контроль.
            </h2>
            <p className="mono text-[11px] uppercase tracking-[0.16em] text-mute">
              product flow
            </p>
          </div>
        </Reveal>

        <Reveal delay={0.08} className="relative mt-12">
          <div className="absolute left-0 right-0 top-[18px] hidden h-px bg-line-strong md:block" />
          {!reduceMotion ? (
            <motion.span
              aria-hidden
              className="absolute top-[14px] hidden h-2.5 w-2.5 rounded-full bg-blue md:block"
              animate={{ left: ["0%", "100%"] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            />
          ) : null}

          <ol className="grid gap-8 md:grid-cols-4 md:gap-6">
            {STEPS.map((step) => (
              <li key={step.code} className="relative">
                <span className="relative z-10 inline-flex h-[10px] w-[10px] rounded-full bg-blue ring-4 ring-bg" />
                <p className="mono mt-5 text-[11px] uppercase tracking-[0.16em] text-mute">
                  {step.code}
                </p>
                <p className="mt-2 text-lg font-semibold tracking-[-0.03em] text-ink">
                  {step.title}
                </p>
                <p className="mono mt-2 text-sm text-mute">{step.meta}</p>
              </li>
            ))}
          </ol>
        </Reveal>
      </Container>
    </section>
  );
}
