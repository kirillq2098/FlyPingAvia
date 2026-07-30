"use client";

import { ArrowRight, Send } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Parallax } from "@/components/ui/Parallax";
import { Reveal } from "@/components/ui/Reveal";
import { ScrollParallax } from "@/components/ui/ScrollParallax";
import { HeroIllustration } from "@/components/HeroIllustration";
import { siteConfig } from "@/lib/site";

export function Hero() {
  const reduceMotion = useReducedMotion();

  return (
    <section className="relative overflow-hidden pb-20 pt-10 sm:pb-28 sm:pt-14 lg:pb-32 lg:pt-16">
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <ScrollParallax
          offset={48}
          className="absolute left-1/2 top-[-12%] h-[580px] w-[920px] -translate-x-1/2"
        >
          <div className="h-full w-full rounded-full bg-[radial-gradient(circle,rgba(56,189,248,0.24),transparent_62%)] blur-3xl" />
        </ScrollParallax>
        <ScrollParallax offset={28} className="absolute -left-28 top-28 h-80 w-80">
          <div className="h-full w-full rounded-full bg-brand-400/20 blur-3xl" />
        </ScrollParallax>
        <ScrollParallax offset={40} className="absolute right-[-5%] top-10 h-[26rem] w-[26rem]">
          <div className="h-full w-full rounded-full bg-sky-300/25 blur-3xl" />
        </ScrollParallax>
        <motion.div
          aria-hidden
          className="absolute left-[10%] top-[44%] h-px w-48 bg-gradient-to-r from-transparent via-brand-400/55 to-transparent"
          animate={reduceMotion ? undefined : { opacity: [0.2, 0.85, 0.2], x: [0, 28, 0] }}
          transition={{ duration: 5.2, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          aria-hidden
          className="absolute right-[14%] top-[62%] h-px w-56 bg-gradient-to-r from-transparent via-sky-400/55 to-transparent"
          animate={reduceMotion ? undefined : { opacity: [0.15, 0.75, 0.15], x: [0, -22, 0] }}
          transition={{ duration: 6.8, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>

      <Container className="grid items-center gap-14 lg:grid-cols-2 lg:gap-16">
        <div>
          <Reveal>
            <p className="mb-5 text-sm font-semibold tracking-[0.2em] text-brand-600 uppercase">
              {siteConfig.name}
            </p>
            <h1 className="max-w-xl text-balance text-4xl font-semibold tracking-[-0.048em] text-ink sm:text-5xl lg:text-[3.7rem] lg:leading-[1.04]">
              Находите дешёвые авиабилеты{" "}
              <span className="gradient-text">первыми.</span>
            </h1>
            <p className="mt-6 max-w-lg text-pretty text-base leading-relaxed text-slate-600 sm:text-lg sm:leading-8">
              FlyPing автоматически отслеживает стоимость авиабилетов и
              моментально сообщает о снижении цены через Telegram.
            </p>
          </Reveal>

          <Reveal delay={0.1} className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button
              href={siteConfig.telegramBotUrl}
              target="_blank"
              rel="noopener noreferrer"
              size="lg"
              className="group"
            >
              <Send className="h-4 w-4 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
              Открыть Telegram-бота
            </Button>
            <Button href="#how-it-works" variant="secondary" size="lg" className="group">
              Узнать подробнее
              <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
            </Button>
          </Reveal>

          <Reveal delay={0.18} className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-slate-500">
            <span className="inline-flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.12)]" />
              Мониторинг 24/7
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-500 shadow-[0_0_0_4px_rgba(37,99,235,0.12)]" />
              Мгновенные алерты
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-sky-400 shadow-[0_0_0_4px_rgba(56,189,248,0.14)]" />
              Без лишних приложений
            </span>
          </Reveal>
        </div>

        <Reveal delay={0.14} y={36} className="relative">
          <Parallax strength={16}>
            <HeroIllustration />
          </Parallax>
        </Reveal>
      </Container>
    </section>
  );
}
