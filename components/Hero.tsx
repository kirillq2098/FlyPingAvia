import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { HeroIllustration } from "@/components/HeroIllustration";
import { siteConfig } from "@/lib/site";

const TRAITS = [
  "настройка за минуту",
  "уведомления в Telegram",
  "можно отключить в любой момент",
] as const;

export function Hero() {
  return (
    <section className="relative pb-16 pt-10 sm:pb-24 sm:pt-14 lg:pb-28 lg:pt-16">
      <Container className="grid items-start gap-12 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:gap-16 lg:items-center">
        <div className="max-w-xl">
          <Reveal>
            <p className="mb-5 text-sm font-medium text-muted">{siteConfig.name}</p>
            <h1 className="display text-balance text-[2.35rem] leading-[1.08] text-ink sm:text-5xl lg:text-[3.35rem] lg:leading-[1.05]">
              Цена на билет изменилась. Вы узнаете первым.
            </h1>
            <p className="mt-5 max-w-[34rem] text-pretty text-base leading-7 text-muted sm:text-lg sm:leading-8">
              FlyPing следит за выбранным маршрутом и присылает сообщение в
              Telegram, когда билет становится дешевле.
            </p>
          </Reveal>

          <Reveal delay={0.08} className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center">
            <Button
              href={siteConfig.telegramBotUrl}
              target="_blank"
              rel="noopener noreferrer"
              size="lg"
            >
              Запустить в Telegram
            </Button>
            <Button href="#how-it-works" variant="secondary" className="text-sm sm:text-[0.95rem]">
              Посмотреть, как это работает
            </Button>
          </Reveal>

          <Reveal delay={0.14}>
            <ul className="mt-8 flex flex-col gap-2 border-t border-line pt-6 text-sm text-muted sm:flex-row sm:flex-wrap sm:gap-x-6 sm:gap-y-2">
              {TRAITS.map((item) => (
                <li key={item} className="inline-flex items-center gap-2">
                  <span className="h-1 w-1 rounded-full bg-brand" aria-hidden />
                  {item}
                </li>
              ))}
            </ul>
          </Reveal>
        </div>

        <Reveal delay={0.1} y={18}>
          <HeroIllustration />
        </Reveal>
      </Container>
    </section>
  );
}
