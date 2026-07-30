"use client";

import { motion, useReducedMotion } from "framer-motion";

export function HeroIllustration() {
  const reduceMotion = useReducedMotion();

  return (
    <div className="relative mx-auto aspect-square w-full max-w-[540px]">
      <div className="absolute inset-0 rounded-[28px] bg-gradient-to-br from-white via-sky-50 to-brand-50 shadow-[0_30px_80px_rgba(37,99,235,0.14)] ring-1 ring-white/80" />
      <div className="absolute -inset-6 -z-10 rounded-[36px] bg-gradient-to-br from-brand-400/20 via-sky-300/10 to-transparent blur-2xl" />

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
          <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect x="36" y="36" width="448" height="448" rx="28" fill="url(#mapFill)" opacity="0.55" />

        <g opacity="0.35" stroke="#94A3B8" strokeWidth="1">
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

        <ellipse cx="180" cy="210" rx="58" ry="34" fill="#BFDBFE" opacity="0.7" />
        <ellipse cx="300" cy="170" rx="42" ry="26" fill="#BAE6FD" opacity="0.75" />
        <ellipse cx="360" cy="250" rx="70" ry="40" fill="#BFDBFE" opacity="0.55" />
        <ellipse cx="150" cy="320" rx="48" ry="28" fill="#BAE6FD" opacity="0.5" />

        <motion.path
          d="M90 340 C160 280, 220 250, 280 230 S400 180, 440 140"
          fill="none"
          stroke="url(#routeStroke)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="8 10"
          initial={false}
          animate={
            reduceMotion
              ? { pathLength: 1, opacity: 1 }
              : { pathLength: 1, opacity: 1 }
          }
          transition={{ duration: 1.6, ease: "easeInOut" }}
        />
        <motion.path
          d="M110 390 C190 330, 250 300, 320 290 S410 250, 450 220"
          fill="none"
          stroke="#38BDF8"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="4 8"
          opacity="0.7"
          initial={false}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.8, delay: 0.2, ease: "easeInOut" }}
        />

        {!reduceMotion ? (
          <motion.g
            filter="url(#softGlow)"
            animate={{
              x: [90, 160, 240, 340, 440],
              y: [340, 280, 235, 180, 140],
              rotate: [8, 4, -2, -8, -16],
            }}
            transition={{
              duration: 6,
              repeat: Infinity,
              ease: "easeInOut",
              repeatType: "loop",
            }}
          >
            <g transform="translate(-14 -14)">
              <circle cx="14" cy="14" r="16" fill="#2563EB" opacity="0.15" />
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

        <g transform="translate(78 78)">
          <rect
            width="180"
            height="120"
            rx="18"
            fill="white"
            fillOpacity="0.92"
            stroke="#E2E8F0"
          />
          <text x="18" y="28" fill="#64748B" fontSize="11" fontFamily="sans-serif">
            Цена билета
          </text>
          <text x="18" y="52" fill="#0F172A" fontSize="22" fontWeight="700" fontFamily="sans-serif">
            −32%
          </text>
          <path
            d="M18 92 C48 88, 70 70, 95 62 S140 58, 162 42"
            fill="none"
            stroke="#2563EB"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <path
            d="M18 92 C48 88, 70 70, 95 62 S140 58, 162 42 V100 H18 Z"
            fill="url(#chartFill)"
          />
          <circle cx="162" cy="42" r="5" fill="#38BDF8" />
        </g>

        <g transform="translate(290 340)">
          <rect
            width="150"
            height="84"
            rx="18"
            fill="white"
            fillOpacity="0.95"
            stroke="#E2E8F0"
          />
          <circle cx="28" cy="42" r="14" fill="#2563EB" />
          <path
            d="M22 42 L26 46 L34 36"
            fill="none"
            stroke="white"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <text x="50" y="38" fill="#0F172A" fontSize="13" fontWeight="700" fontFamily="sans-serif">
            Цена снизилась
          </text>
          <text x="50" y="58" fill="#64748B" fontSize="11" fontFamily="sans-serif">
            Telegram · сейчас
          </text>
        </g>
      </svg>
    </div>
  );
}
