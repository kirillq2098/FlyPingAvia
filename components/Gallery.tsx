"use client";

import { motion } from "framer-motion";
import { ImageIcon } from "lucide-react";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { GALLERY_ITEMS } from "@/lib/constants";

export function Gallery() {
  return (
    <section id="gallery" className="relative scroll-mt-24 py-20 sm:py-24">
      <Container>
        <Reveal>
          <SectionHeading
            eyebrow="Скриншоты"
            title="Так выглядит работа с FlyPing"
            description="Пока здесь аккуратные заглушки — позже заменим их на реальные скриншоты бота."
          />
        </Reveal>

        <div className="mt-14 grid gap-5 md:grid-cols-3">
          {GALLERY_ITEMS.map((item, index) => (
            <Reveal key={item.id} delay={index * 0.08}>
              <motion.figure
                whileHover={{ y: -6, scale: 1.02 }}
                transition={{ type: "spring", stiffness: 280, damping: 20 }}
                className="overflow-hidden rounded-[24px] border border-slate-200/80 bg-white shadow-[0_16px_40px_rgba(15,23,42,0.05)]"
              >
                <div className="relative flex aspect-[4/5] items-center justify-center bg-gradient-to-br from-slate-50 via-brand-50/40 to-sky-50">
                  <div className="absolute inset-6 rounded-[20px] border border-dashed border-slate-300/80 bg-white/50" />
                  <div className="relative z-10 flex flex-col items-center gap-3 text-slate-500">
                    <span className="inline-flex h-14 w-14 items-center justify-center rounded-[18px] bg-white shadow-[0_10px_24px_rgba(15,23,42,0.08)] ring-1 ring-slate-200/80">
                      <ImageIcon className="h-6 w-6 text-brand-500" />
                    </span>
                    <span className="text-sm font-medium">Скриншот {index + 1}</span>
                  </div>
                </div>
                <figcaption className="space-y-1 px-5 py-4">
                  <p className="font-semibold text-ink">{item.title}</p>
                  <p className="text-sm text-slate-600">{item.description}</p>
                </figcaption>
              </motion.figure>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
