"use client";

import { motion, useReducedMotion } from "framer-motion";
import { DEMO_ROUTE, formatRub } from "@/lib/constants";

export function HeroIllustration() {
  const reduceMotion = useReducedMotion();

  return (
    <div className="relative mx-auto w-full max-w-[420px]">
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
        className="rounded-[var(--radius-lg)] border border-line bg-surface-raised p-5 shadow-[var(--shadow)] sm:p-6"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-[10px] bg-brand text-sm font-bold text-white">
              FP
            </span>
            <div>
              <p className="text-sm font-semibold text-ink">FlyPing</p>
              <p className="text-sm text-muted">Telegram · бот</p>
            </div>
          </div>
          <p className="text-xs text-muted">2 мин назад</p>
        </div>

        <div className="mt-5 border-t border-line pt-5">
          <p className="text-sm font-medium text-ink">Цена снизилась</p>
          <div className="mt-3 flex items-center gap-3 text-sm text-muted">
            <span className="font-medium text-ink">{DEMO_ROUTE.originCode}</span>
            <span aria-hidden className="h-px flex-1 bg-line-strong" />
            <span className="font-medium text-ink">{DEMO_ROUTE.destinationCode}</span>
          </div>
          <p className="mt-2 text-sm text-muted">
            {DEMO_ROUTE.origin} → {DEMO_ROUTE.destination}
          </p>
          <p className="mt-1 text-sm text-muted">{DEMO_ROUTE.dates}</p>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3">
          <div className="rounded-[var(--radius)] border border-line bg-surface px-3 py-3">
            <p className="text-xs text-muted">Было</p>
            <p className="tabular mt-1 text-lg font-semibold text-muted line-through decoration-line-strong">
              {formatRub(DEMO_ROUTE.oldPrice)}
            </p>
          </div>
          <div className="rounded-[var(--radius)] border border-gain/20 bg-gain-soft px-3 py-3">
            <p className="text-xs text-gain">Стало</p>
            <motion.p
              className="tabular mt-1 text-lg font-semibold text-gain"
              initial={reduceMotion ? false : { opacity: 0.4 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.25 }}
            >
              {formatRub(DEMO_ROUTE.newPrice)}
            </motion.p>
          </div>
        </div>

        <p className="tabular mt-4 text-sm font-medium text-gain">
          −{formatRub(DEMO_ROUTE.drop)}
        </p>

        <PriceSparkline />

        <button
          type="button"
          className="mt-5 flex h-11 w-full items-center justify-center rounded-[var(--radius)] bg-brand text-sm font-medium text-white transition-colors hover:bg-brand-hover"
        >
          Посмотреть билет
        </button>
      </motion.div>

      <motion.div
        aria-hidden
        initial={reduceMotion ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15 }}
        className="absolute -right-2 -top-3 rounded-[var(--radius)] border border-line bg-surface-raised px-3 py-2 text-xs text-muted shadow-[var(--shadow-soft)] sm:-right-4"
      >
        обнаружено 2 минуты назад
      </motion.div>
    </div>
  );
}

function PriceSparkline() {
  const reduceMotion = useReducedMotion();

  return (
    <div className="mt-5">
      <div className="mb-2 flex items-center justify-between text-xs text-muted">
        <span>История цены</span>
        <span>7 дней</span>
      </div>
      <svg viewBox="0 0 320 72" className="h-16 w-full" role="img" aria-label="График снижения цены">
        <path
          d="M8 22 C48 20, 72 34, 104 38 S160 28, 196 30 S250 48, 312 54"
          fill="none"
          stroke="#c9c3b8"
          strokeWidth="1.5"
          strokeDasharray="4 4"
        />
        <motion.path
          d="M8 22 C48 20, 72 34, 104 38 S160 28, 196 30 S236 44, 268 18 S300 14, 312 12"
          fill="none"
          stroke="#1a3f8b"
          strokeWidth="2"
          strokeLinecap="round"
          initial={reduceMotion ? false : { pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.1, ease: "easeInOut" }}
        />
        <motion.circle
          cx="312"
          cy="12"
          r="4"
          fill="#1f6b45"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.9 }}
        />
      </svg>
    </div>
  );
}
