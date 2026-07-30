import { ArrowRight, Send } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { HeroIllustration } from "@/components/HeroIllustration";
import { siteConfig } from "@/lib/site";

export function Hero() {
  return (
    <section className="relative overflow-hidden pb-16 pt-10 sm:pb-24 sm:pt-16 lg:pb-28 lg:pt-20">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-0 h-[520px] w-[820px] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(56,189,248,0.18),transparent_65%)] blur-2xl" />
        <div className="absolute -left-24 top-40 h-72 w-72 rounded-full bg-brand-400/15 blur-3xl" />
        <div className="absolute right-0 top-24 h-80 w-80 rounded-full bg-sky-300/20 blur-3xl" />
      </div>

      <Container className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
        <div>
          <Reveal>
            <p className="mb-5 text-sm font-semibold tracking-[0.18em] text-brand-600 uppercase">
              {siteConfig.name}
            </p>
            <h1 className="max-w-xl text-balance text-4xl font-semibold tracking-tight text-ink sm:text-5xl lg:text-[3.5rem] lg:leading-[1.08]">
              Находите дешёвые авиабилеты первыми.
            </h1>
            <p className="mt-5 max-w-lg text-pretty text-base leading-relaxed text-slate-600 sm:text-lg">
              FlyPing автоматически отслеживает стоимость авиабилетов и
              моментально сообщает о снижении цены через Telegram.
            </p>
          </Reveal>

          <Reveal delay={0.12} className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button
              href={siteConfig.telegramBotUrl}
              target="_blank"
              rel="noopener noreferrer"
              size="lg"
              className="group"
            >
              <Send className="h-4 w-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
              Открыть Telegram-бота
            </Button>
            <Button href="#how-it-works" variant="secondary" size="lg" className="group">
              Узнать подробнее
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Button>
          </Reveal>
        </div>

        <Reveal delay={0.18} y={32}>
          <HeroIllustration />
        </Reveal>
      </Container>
    </section>
  );
}
