"use client";

import { Send } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { siteConfig } from "@/lib/site";

export function CTA() {
  const reduceMotion = useReducedMotion();

  return (
    <section id="cta" className="section-fade relative scroll-mt-24 py-16 sm:py-24">
      <Container>
        <Reveal>
          <div className="relative overflow-hidden rounded-[30px] bg-gradient-to-br from-brand-700 via-brand-500 to-sky-400 px-6 py-16 text-center shadow-[0_36px_90px_rgba(37,99,235,0.38)] sm:px-12 sm:py-20">
            <div className="pointer-events-none absolute -left-12 -top-12 h-56 w-56 rounded-full bg-white/15 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-20 -right-10 h-64 w-64 rounded-full bg-sky-200/35 blur-3xl" />
            <div className="pointer-events-none absolute inset-0 opacity-25 [background-image:linear-gradient(rgba(255,255,255,0.18)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.18)_1px,transparent_1px)] [background-size:28px_28px]" />

            <motion.div
              aria-hidden
              className="pointer-events-none absolute left-[18%] top-[34%] h-px w-40 bg-gradient-to-r from-transparent via-white/70 to-transparent"
              animate={reduceMotion ? undefined : { opacity: [0.2, 0.8, 0.2], x: [0, 30, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
            />

            <div className="relative mx-auto max-w-2xl">
              <h2 className="text-balance text-3xl font-semibold tracking-[-0.04em] text-white sm:text-4xl lg:text-5xl lg:leading-[1.08]">
                Попробуйте FlyPing уже сегодня.
              </h2>
              <p className="mt-4 text-base text-sky-50/90 sm:text-lg sm:leading-8">
                Откройте Telegram-бота и начните отслеживать цены на авиабилеты за пару минут.
              </p>
              <div className="mt-9 flex justify-center">
                <Button
                  href={siteConfig.telegramBotUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  size="lg"
                  className="group bg-white text-brand-700 shadow-[0_14px_34px_rgba(15,23,42,0.2)] ring-0 hover:bg-sky-50 hover:shadow-[0_18px_40px_rgba(15,23,42,0.24)]"
                >
                  <Send className="h-4 w-4 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                  Открыть Telegram
                </Button>
              </div>
            </div>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
