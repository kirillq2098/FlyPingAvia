"use client";

import { motion, useReducedMotion } from "framer-motion";

const ROUTE_A = "M90 340 C160 280, 220 250, 280 230 S400 180, 440 140";
const ROUTE_B = "M110 390 C190 330, 250 300, 320 290 S410 250, 450 220";
const ROUTE_C = "M70 260 C150 220, 240 210, 330 170 S430 110, 470 90";

export function HeroIllustration() {
  const reduceMotion = useReducedMotion();

  return (
    <div className="relative mx-auto aspect-square w-full max-w-[540px]">
      <div className="absolute inset-0 rounded-[30px] bg-gradient-to-br from-white via-sky-50/90 to-brand-50/90 shadow-[0_40px_100px_rgba(37,99,235,0.16)] ring-1 ring-white/90" />
      <div className="absolute -inset-8 -z-10 rounded-[40px] bg-gradient-to-br from-brand-400/25 via-sky-300/15 to-transparent blur-3xl" />
      <div className="animate-pulse-soft absolute right-8 top-10 h-24 w-24 rounded-full bg-sky-300/30 blur-2xl" />
      <div className="animate-float absolute left-6 bottom-16 h-20 w-20 rounded-full bg-brand-400/25 blur-2xl" />

      <svg
        viewBox="0 0 520 520"
        className="relative h-full w-full"
        role="img"
        aria-label="Иллюстрация мониторинга авиабилетов: карта, маршруты и снижение цены"
      >
        <defs>
          <linearGradient id="mapFill" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#DBEAFE" />
            <stop offset="100%" stopColor="#E0F2FE" />
          </linearGradient>
          <linearGradient id="routeStroke" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#2563EB" />
            <stop offset="100%" stopColor="#38BDF8" />
          </linearGradient>
          <linearGradient id="chartFill" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(37,99,235,0.28)" />
            <stop offset="100%" stopColor="rgba(37,99,235,0)" />
          </linearGradient>
          <filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect x="36" y="36" width="448" height="448" rx="30" fill="url(#mapFill)" opacity="0.5" />

        <g opacity="0.28" stroke="#94A3B8" strokeWidth="1">
          {Array.from({ length: 8 }).map((_, index) => (
            <line
              key={`h-${index}`}
              x1="60"
              x2="460"
              y1={80 + index * 44}
              y2={80 + index * 44}
            />
          ))}
          {Array.from({ length: 8 }).map((_, index) => (
            <line
              key={`v-${index}`}
              y1="60"
              y2="460"
              x1={80 + index * 48}
              x2={80 + index * 48}
            />
          ))}
        </g>

        <ellipse cx="180" cy="210" rx="58" ry="34" fill="#BFDBFE" opacity="0.72" />
        <ellipse cx="300" cy="170" rx="42" ry="26" fill="#BAE6FD" opacity="0.78" />
        <ellipse cx="360" cy="250" rx="70" ry="40" fill="#BFDBFE" opacity="0.55" />
        <ellipse cx="150" cy="320" rx="48" ry="28" fill="#BAE6FD" opacity="0.5" />

        <path
          d={ROUTE_A}
          fill="none"
          stroke="url(#routeStroke)"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeDasharray="9 11"
          className={reduceMotion ? undefined : "animate-dash"}
          opacity="0.95"
        />
        <path
          d={ROUTE_B}
          fill="none"
          stroke="#38BDF8"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeDasharray="5 9"
          className={reduceMotion ? undefined : "animate-dash"}
          opacity="0.7"
        />
        <path
          d={ROUTE_C}
          fill="none"
          stroke="#60A5FA"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeDasharray="3 8"
          className={reduceMotion ? undefined : "animate-dash"}
          opacity="0.55"
        />

        <circle cx="90" cy="340" r="4" fill="#2563EB" />
        <circle cx="440" cy="140" r="4" fill="#38BDF8" />
        <circle cx="110" cy="390" r="3.5" fill="#38BDF8" opacity="0.8" />
        <circle cx="450" cy="220" r="3.5" fill="#2563EB" opacity="0.8" />

        {!reduceMotion ? (
          <motion.g
            filter="url(#softGlow)"
            animate={{
              x: [90, 170, 260, 350, 440],
              y: [340, 275, 235, 185, 140],
              rotate: [10, 4, -2, -10, -18],
            }}
            transition={{
              duration: 7.5,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          >
            <g transform="translate(-14 -14)">
              <circle cx="14" cy="14" r="18" fill="#2563EB" opacity="0.14" />
              <path
                d="M6 16 L22 12 L26 14 L22 16 L14 18 L10 24 L8 18 L2 16 Z"
                fill="#2563EB"
              />
              <path d="M8 14 L18 11" stroke="#7DD3FC" strokeWidth="1.5" />
            </g>
          </motion.g>
        ) : (
          <g transform="translate(260 220)" filter="url(#softGlow)">
            <circle cx="14" cy="14" r="16" fill="#2563EB" opacity="0.15" />
            <path
              d="M6 16 L22 12 L26 14 L22 16 L14 18 L10 24 L8 18 L2 16 Z"
              fill="#2563EB"
            />
          </g>
        )}

        <motion.g
          transform="translate(78 78)"
          animate={reduceMotion ? undefined : { y: [0, -6, 0] }}
          transition={{ duration: 4.8, repeat: Infinity, ease: "easeInOut" }}
        >
          <rect
            width="186"
            height="124"
            rx="20"
            fill="rgba(255,255,255,0.88)"
            stroke="rgba(226,232,240,0.95)"
          />
          <text x="18" y="30" fill="#64748B" fontSize="11" fontFamily="sans-serif">
            Цена билета
          </text>
          <text x="18" y="56" fill="#0F172A" fontSize="24" fontWeight="700" fontFamily="sans-serif">
            −32%
          </text>
          <path
            d="M18 96 C48 92, 70 74, 95 66 S140 62, 164 46"
            fill="none"
            stroke="#2563EB"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <path
            d="M18 96 C48 92, 70 74, 95 66 S140 62, 164 46 V104 H18 Z"
            fill="url(#chartFill)"
          />
          <circle cx="164" cy="46" r="5" fill="#38BDF8" />
        </motion.g>

        <motion.g
          transform="translate(286 338)"
          animate={reduceMotion ? undefined : { y: [0, 7, 0] }}
          transition={{ duration: 5.4, repeat: Infinity, ease: "easeInOut", delay: 0.4 }}
        >
          <rect
            width="156"
            height="88"
            rx="20"
            fill="rgba(255,255,255,0.92)"
            stroke="rgba(226,232,240,0.95)"
          />
          <circle cx="30" cy="44" r="15" fill="#2563EB" />
          <path
            d="M24 44 L28 48 L36 38"
            fill="none"
            stroke="white"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <text x="54" y="40" fill="#0F172A" fontSize="13" fontWeight="700" fontFamily="sans-serif">
            Цена снизилась
          </text>
          <text x="54" y="60" fill="#64748B" fontSize="11" fontFamily="sans-serif">
            Telegram · сейчас
          </text>
        </motion.g>
      </svg>
    </div>
  );
}
