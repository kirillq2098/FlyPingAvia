"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { siteConfig } from "@/lib/site";

export function CTA() {
  const reduceMotion = useReducedMotion();

  return (
    <section id="cta" className="scroll-mt-24 bg-navy py-20 text-white sm:py-28">
      <Container>
        <Reveal>
          <div className="flex items-center justify-between gap-6 border-b border-navy-line pb-8">
            <p className="airport-code text-4xl sm:text-6xl">OVB</p>
            <div className="relative mx-4 h-px flex-1 bg-navy-line">
              {!reduceMotion ? (
                <motion.span
                  aria-hidden
                  className="absolute top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full bg-white"
                  animate={{ left: ["0%", "100%"] }}
                  transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
                />
              ) : (
                <span className="absolute left-1/2 top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white" />
              )}
            </div>
            <p className="airport-code text-4xl sm:text-6xl">LED</p>
          </div>

          <div className="mt-10 max-w-3xl">
            <h2 className="text-balance text-4xl font-semibold leading-[1.05] tracking-[-0.045em] sm:text-5xl lg:text-[3.5rem]">
              Следующий выгодный билет
              <br />
              не должен пройти незамеченным.
            </h2>
            <div className="mt-8">
              <Button
                href={siteConfig.telegramBotUrl}
                target="_blank"
                rel="noopener noreferrer"
                size="lg"
                variant="on-dark"
              >
                Запустить FlyPing
              </Button>
            </div>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
