"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { DEMO_ROUTE, formatRub } from "@/lib/constants";

const CHECKS = [
  { time: "06:40", note: "проверка" },
  { time: "11:15", note: "без изменений" },
  { time: "16:02", note: "небольшое снижение" },
  { time: "19:48", note: "уведомление отправлено" },
] as const;

export function PriceDrop() {
  const reduceMotion = useReducedMotion();

  return (
    <section id="price-drop" className="scroll-mt-24 bg-night py-20 text-white sm:py-28">
      <Container>
        <div className="grid gap-12 lg:grid-cols-[1.1fr_0.9fr] lg:items-end lg:gap-16">
          <Reveal>
            <p className="text-sm font-medium text-night-muted">Сценарий снижения</p>
            <h2 className="display mt-3 max-w-xl text-balance text-3xl leading-[1.12] sm:text-4xl lg:text-[2.9rem]">
              {formatRub(DEMO_ROUTE.oldPrice)} → {formatRub(DEMO_ROUTE.newPrice)}
            </h2>
            <p className="mt-5 max-w-md text-base leading-7 text-night-muted sm:text-lg sm:leading-8">
              Как только цена становится ниже, FlyPing отправляет уведомление.
            </p>

            <div className="mt-10 overflow-hidden rounded-[var(--radius-lg)] border border-night-line bg-night-elevated p-5 sm:p-6">
              <div className="mb-4 flex items-end justify-between gap-4">
                <div>
                  <p className="text-sm text-night-muted">
                    {DEMO_ROUTE.origin} → {DEMO_ROUTE.destination}
                  </p>
                  <p className="mt-1 text-sm text-night-muted">{DEMO_ROUTE.dates}</p>
                </div>
                <p className="tabular text-sm font-medium text-[#7dcea0]">
                  −{formatRub(DEMO_ROUTE.drop)}
                </p>
              </div>

              <svg
                viewBox="0 0 640 220"
                className="h-44 w-full sm:h-52"
                role="img"
                aria-label="График изменения цены билета"
              >
                <line x1="24" y1="180" x2="616" y2="180" stroke="#2a303c" strokeWidth="1" />
                <line x1="24" y1="40" x2="24" y2="180" stroke="#2a303c" strokeWidth="1" />
                <path
                  d="M40 58 C120 55, 180 70, 240 78 S360 92, 420 110 S520 150, 600 168"
                  fill="none"
                  stroke="#3b4556"
                  strokeWidth="2"
                />
                <motion.path
                  d="M40 58 C120 55, 180 70, 240 78 S340 86, 400 70 S500 48, 600 36"
                  fill="none"
                  stroke="#8fb4ff"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  initial={reduceMotion ? false : { pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 1.2, ease: "easeInOut" }}
                />
                <motion.circle
                  cx="600"
                  cy="36"
                  r="5"
                  fill="#7dcea0"
                  initial={reduceMotion ? false : { scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 1, type: "spring", stiffness: 260, damping: 18 }}
                />
                <text x="40" y="48" fill="#9aa3b2" fontSize="12">
                  {formatRub(DEMO_ROUTE.oldPrice)}
                </text>
                <text x="500" y="28" fill="#7dcea0" fontSize="12">
                  {formatRub(DEMO_ROUTE.newPrice)}
                </text>
              </svg>
            </div>
          </Reveal>

          <Reveal delay={0.1}>
            <p className="text-sm font-medium text-night-muted">Временная шкала проверок</p>
            <ol className="mt-5 space-y-0 border-l border-night-line">
              {CHECKS.map((item, index) => (
                <li key={item.time} className="relative py-4 pl-6">
                  <span
                    className={cnDot(index === CHECKS.length - 1)}
                    aria-hidden
                  />
                  <p className="tabular text-sm font-medium text-white">{item.time}</p>
                  <p className="mt-1 text-sm text-night-muted">{item.note}</p>
                </li>
              ))}
            </ol>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}

function cnDot(active: boolean): string {
  return [
    "absolute -left-[5px] top-5 h-2.5 w-2.5 rounded-full border",
    active
      ? "border-[#7dcea0] bg-[#7dcea0]"
      : "border-night-line bg-night",
  ].join(" ");
}
