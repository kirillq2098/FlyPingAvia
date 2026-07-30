"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { CHAT_ROUTE, formatRub } from "@/lib/constants";

export function Gallery() {
  const reduceMotion = useReducedMotion();

  return (
    <section id="gallery" className="scroll-mt-24 border-y border-line bg-surface py-20 sm:py-24">
      <Container className="grid items-center gap-12 lg:grid-cols-[0.95fr_1.05fr] lg:gap-16">
        <Reveal>
          <SectionHeading
            eyebrow="Пример диалога"
            title="Так выглядит общение с FlyPing"
            description="Короткие сообщения. Понятный маршрут. Уведомление о снижении без лишнего шума."
          />
        </Reveal>

        <Reveal delay={0.08}>
          <div className="mx-auto w-full max-w-[360px]">
            <div className="rounded-[28px] border border-line bg-[#1c1c1e] p-3 shadow-[var(--shadow)]">
              <div className="overflow-hidden rounded-[22px] bg-[#efeae2]">
                <div className="flex items-center gap-3 border-b border-[#ddd6cb] bg-[#f7f3ec] px-4 py-3">
                  <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-brand text-xs font-bold text-white">
                    FP
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-ink">FlyPing</p>
                    <p className="text-xs text-muted">бот</p>
                  </div>
                </div>

                <div className="space-y-3 px-4 py-5">
                  <ChatBubble side="user">
                    {CHAT_ROUTE.origin} — {CHAT_ROUTE.destination}, {CHAT_ROUTE.dates}
                  </ChatBubble>

                  <motion.div
                    initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.15, duration: 0.35 }}
                  >
                    <ChatBubble side="bot">
                      Маршрут добавлен. Сообщу, когда цена снизится.
                    </ChatBubble>
                  </motion.div>

                  <p className="py-2 text-center text-xs text-muted">позже</p>

                  <motion.div
                    initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.3, duration: 0.35 }}
                  >
                    <ChatBubble side="bot" accent>
                      Цена снизилась на {formatRub(CHAT_ROUTE.drop)}.
                    </ChatBubble>
                  </motion.div>
                </div>
              </div>
            </div>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}

function ChatBubble({
  children,
  side,
  accent = false,
}: {
  children: React.ReactNode;
  side: "user" | "bot";
  accent?: boolean;
}) {
  const isUser = side === "user";
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div
        className={[
          "max-w-[85%] rounded-[16px] px-3.5 py-2.5 text-sm leading-6",
          isUser
            ? "rounded-br-[6px] bg-brand text-white"
            : accent
              ? "rounded-bl-[6px] bg-gain-soft text-gain"
              : "rounded-bl-[6px] bg-white text-ink shadow-[var(--shadow-soft)]",
        ].join(" ")}
      >
        {children}
      </div>
    </div>
  );
}
