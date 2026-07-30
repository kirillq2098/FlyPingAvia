import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { RouteBoard } from "@/components/RouteBoard";
import { ANALYTICS_EVENTS } from "@/lib/analytics";
import { siteConfig } from "@/lib/config";

export function Hero() {
  return (
    <section className="pb-16 pt-10 sm:pb-20 sm:pt-14 lg:pb-24 lg:pt-16">
      <Container>
        <div className="grid items-end gap-10 lg:grid-cols-12 lg:gap-8">
          <Reveal className="lg:col-span-7">
            <p className="mono text-[11px] uppercase tracking-[0.18em] text-mute">
              price monitoring · telegram
            </p>
            <h1 className="mt-5 max-w-[11ch] text-balance text-[3.1rem] font-semibold leading-[0.98] tracking-[-0.055em] text-ink sm:text-6xl lg:text-[5.5rem] lg:leading-[0.94]">
              Билет подешевел.
              <br />
              FlyPing уже сообщил.
            </h1>
          </Reveal>

          <Reveal delay={0.08} className="lg:col-span-5 lg:pb-2">
            <p className="max-w-md text-base leading-7 text-mute sm:text-[1.05rem] sm:leading-8">
              Укажите маршрут один раз. FlyPing будет следить за ценой и отправит
              сообщение в Telegram, когда появится более выгодный билет.
            </p>
            <div className="mt-7 flex flex-col gap-4 sm:flex-row sm:items-center">
              <Button
                href={siteConfig.telegramBotUrl}
                target="_blank"
                rel="noopener noreferrer"
                size="lg"
                eventName={ANALYTICS_EVENTS.telegramOpenHero}
              >
                Начать отслеживание
              </Button>
              <Button href="#example" variant="link" className="text-sm text-mute hover:text-ink">
                Посмотреть пример уведомления
              </Button>
            </div>
          </Reveal>
        </div>

        <Reveal delay={0.12} className="mt-12 lg:mt-16">
          <div id="example">
            <RouteBoard />
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
