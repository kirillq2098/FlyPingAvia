"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { cn } from "@/lib/cn";

const STEPS = [
  {
    id: "origin",
    title: "Откуда",
    detail: "Новосибирск (OVB)",
    hint: "Город вылета",
  },
  {
    id: "destination",
    title: "Куда",
    detail: "Санкт-Петербург (LED)",
    hint: "Направление",
  },
  {
    id: "dates",
    title: "Даты",
    detail: "12–19 сентября",
    hint: "Окно поездки",
  },
  {
    id: "price",
    title: "Желаемая цена",
    detail: "до 15 000 ₽",
    hint: "Порог уведомления",
  },
  {
    id: "confirm",
    title: "Готово",
    detail: "Маршрут отслеживается",
    hint: "Подтверждение",
  },
] as const;

export function HowItWorks() {
  const [active, setActive] = useState(0);
  const current = STEPS[active];

  return (
    <section id="how-it-works" className="scroll-mt-24 py-20 sm:py-24">
      <Container>
        <Reveal>
          <SectionHeading
            eyebrow="Настройка"
            title="Настройте один раз"
            description="Один сценарий в Telegram — дальше FlyPing сам следит за маршрутом."
          />
        </Reveal>

        <Reveal delay={0.08} className="mt-12 grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:gap-12">
          <ol className="space-y-2">
            {STEPS.map((step, index) => {
              const selected = index === active;
              return (
                <li key={step.id}>
                  <button
                    type="button"
                    onClick={() => setActive(index)}
                    className={cn(
                      "flex w-full items-center justify-between gap-4 rounded-[var(--radius)] border px-4 py-3.5 text-left transition-colors",
                      selected
                        ? "border-brand bg-brand-soft"
                        : "border-transparent hover:border-line hover:bg-surface",
                    )}
                  >
                    <span className="flex items-center gap-3">
                      <span
                        className={cn(
                          "tabular inline-flex h-7 w-7 items-center justify-center rounded-[8px] text-xs font-semibold",
                          selected
                            ? "bg-brand text-white"
                            : "bg-surface-raised text-muted ring-1 ring-line",
                        )}
                      >
                        {index + 1}
                      </span>
                      <span>
                        <span className="block text-sm font-medium text-ink">
                          {step.title}
                        </span>
                        <span className="block text-sm text-muted">{step.hint}</span>
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>

          <div className="rounded-[var(--radius-lg)] border border-line bg-surface-raised p-5 shadow-[var(--shadow-soft)] sm:p-7">
            <div className="flex items-center justify-between border-b border-line pb-4">
              <div>
                <p className="text-sm text-muted">FlyPing · настройка маршрута</p>
                <p className="mt-1 text-lg font-semibold tracking-[-0.02em] text-ink">
                  {current.title}
                </p>
              </div>
              <p className="tabular text-sm text-muted">
                шаг {active + 1}/{STEPS.length}
              </p>
            </div>

            <motion.div
              key={current.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28 }}
              className="mt-6"
            >
              <p className="text-sm text-muted">{current.hint}</p>
              <p className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl">
                {current.detail}
              </p>

              <div className="mt-8 space-y-3">
                {STEPS.slice(0, active + 1).map((step) => (
                  <div
                    key={step.id}
                    className="flex items-center justify-between rounded-[var(--radius)] border border-line bg-surface px-4 py-3"
                  >
                    <span className="text-sm text-muted">{step.title}</span>
                    <span className="text-sm font-medium text-ink">{step.detail}</span>
                  </div>
                ))}
              </div>

              {active === STEPS.length - 1 ? (
                <p className="mt-6 rounded-[var(--radius)] bg-gain-soft px-4 py-3 text-sm font-medium text-gain">
                  Отслеживание включено. Сообщим, когда цена снизится.
                </p>
              ) : (
                <button
                  type="button"
                  onClick={() => setActive((value) => Math.min(value + 1, STEPS.length - 1))}
                  className="mt-6 inline-flex h-11 items-center rounded-[var(--radius)] bg-brand px-5 text-sm font-medium text-white transition-colors hover:bg-brand-hover"
                >
                  Далее
                </button>
              )}
            </motion.div>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
