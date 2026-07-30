"use client";

import { ImageIcon } from "lucide-react";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { SpotlightCard } from "@/components/ui/SpotlightCard";
import { GALLERY_ITEMS } from "@/lib/constants";

export function Gallery() {
  return (
    <section
      id="gallery"
      className="section-divider section-fade relative scroll-mt-24 py-20 sm:py-24"
    >
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
              <SpotlightCard className="overflow-hidden">
                <figure className="h-full">
                  <div className="relative flex aspect-[4/5] items-center justify-center bg-gradient-to-br from-slate-50 via-brand-50/50 to-sky-50">
                    <div className="absolute inset-0 opacity-40 [background-image:linear-gradient(rgba(37,99,235,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(37,99,235,0.08)_1px,transparent_1px)] [background-size:24px_24px]" />
                    <div className="absolute inset-6 rounded-[20px] border border-dashed border-slate-300/70 bg-white/45 backdrop-blur-sm" />
                    <div className="relative z-10 flex flex-col items-center gap-3 text-slate-500">
                      <span className="inline-flex h-14 w-14 items-center justify-center rounded-[18px] bg-white/90 shadow-[0_12px_28px_rgba(15,23,42,0.08)] ring-1 ring-slate-200/80 transition-transform duration-300 group-hover:scale-105">
                        <ImageIcon className="h-6 w-6 text-brand-500" />
                      </span>
                      <span className="text-sm font-medium">Скриншот {index + 1}</span>
                    </div>
                  </div>
                  <figcaption className="space-y-1 px-5 py-4">
                    <p className="font-semibold tracking-[-0.015em] text-ink">{item.title}</p>
                    <p className="text-sm text-slate-600">{item.description}</p>
                  </figcaption>
                </figure>
              </SpotlightCard>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
