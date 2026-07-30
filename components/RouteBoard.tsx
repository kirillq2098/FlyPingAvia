"use client";

import Image from "next/image";
import { motion, useReducedMotion } from "framer-motion";
import { ROUTE, formatRub } from "@/lib/constants";

export function RouteBoard() {
  const reduceMotion = useReducedMotion();

  return (
    <div className="relative overflow-hidden rounded-[14px] border border-line bg-bg-elevated">
      <div className="grid lg:grid-cols-[1.15fr_0.85fr]">
        <div className="relative min-h-[280px] border-b border-line lg:min-h-[420px] lg:border-b-0 lg:border-r">
          <Image
            src="/images/flyping-hero-travel.webp"
            alt="Вид из окна самолёта на облака в золотой час"
            fill
            priority
            sizes="(max-width: 1024px) 100vw, 60vw"
            className="object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#07111f]/75 via-[#07111f]/15 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 p-5 sm:p-7">
            <p className="mono text-[11px] uppercase tracking-[0.18em] text-white/70">
              local time · {ROUTE.departLocal}
            </p>
            <div className="mt-4 flex items-end justify-between gap-4">
              <div>
                <p className="airport-code text-5xl text-white sm:text-6xl">{ROUTE.originCode}</p>
                <p className="mt-2 text-sm text-white/75">{ROUTE.origin}</p>
              </div>
              <RouteLine dark />
              <div className="text-right">
                <p className="airport-code text-5xl text-white sm:text-6xl">
                  {ROUTE.destinationCode}
                </p>
                <p className="mt-2 text-sm text-white/75">{ROUTE.destination}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col justify-between p-5 sm:p-7">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="mono text-[11px] uppercase tracking-[0.16em] text-mute">
                boarding notice
              </p>
              <p className="mt-2 text-sm font-medium text-ink">Уведомление отправлено</p>
            </div>
            <p className="mono text-xs text-mute">{ROUTE.checkedAt}</p>
          </div>

          <div className="my-8">
            <p className="mono text-[11px] uppercase tracking-[0.16em] text-mute">
              {ROUTE.dates}
            </p>
            <div className="mt-4 space-y-2">
              <p className="mono text-2xl text-mute line-through decoration-line-strong sm:text-3xl">
                {formatRub(ROUTE.oldPrice)}
              </p>
              <motion.p
                className="mono text-4xl font-semibold text-ink sm:text-5xl"
                initial={reduceMotion ? false : { opacity: 0.35 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.7, delay: 0.15 }}
              >
                {formatRub(ROUTE.newPrice)}
              </motion.p>
              <p className="mono text-sm font-medium text-gain">
                −{formatRub(ROUTE.drop)}
              </p>
            </div>
          </div>

          <motion.div
            initial={reduceMotion ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.35 }}
            className="rounded-[8px] border border-line bg-bg p-4"
          >
            <div className="flex items-center gap-3">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-blue text-[10px] font-bold text-white">
                FP
              </span>
              <div>
                <p className="text-sm font-medium text-ink">FlyPing</p>
                <p className="mono text-[11px] text-mute">Telegram</p>
              </div>
            </div>
            <p className="mt-3 text-sm leading-6 text-ink">
              {ROUTE.originCode} → {ROUTE.destinationCode}: цена снизилась на{" "}
              <span className="mono font-medium text-gain">
                {formatRub(ROUTE.drop)}
              </span>
              .
            </p>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

function RouteLine({ dark = false }: { dark?: boolean }) {
  const reduceMotion = useReducedMotion();
  const stroke = dark ? "rgba(255,255,255,0.55)" : "#0B4DB8";
  const fill = dark ? "#ffffff" : "#0B4DB8";

  return (
    <svg
      viewBox="0 0 120 24"
      className="mb-8 h-6 w-20 shrink-0 sm:w-28"
      aria-hidden
    >
      <path
        d="M4 12 H116"
        stroke={stroke}
        strokeWidth="1.5"
        strokeDasharray="3 4"
      />
      <circle cx="4" cy="12" r="3" fill={fill} />
      <circle cx="116" cy="12" r="3" fill={fill} />
      {!reduceMotion ? (
        <motion.circle
          cx="4"
          cy="12"
          r="2.5"
          fill={fill}
          animate={{ cx: [4, 116] }}
          transition={{ duration: 3.8, repeat: Infinity, ease: "easeInOut" }}
        />
      ) : null}
    </svg>
  );
}
