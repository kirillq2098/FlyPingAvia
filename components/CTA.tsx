import { Send } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { siteConfig } from "@/lib/site";

export function CTA() {
  return (
    <section id="cta" className="relative scroll-mt-24 py-16 sm:py-24">
      <Container>
        <Reveal>
          <div className="relative overflow-hidden rounded-[28px] bg-gradient-to-br from-brand-600 via-brand-500 to-sky-400 px-6 py-14 text-center shadow-[0_30px_80px_rgba(37,99,235,0.35)] sm:px-12 sm:py-16">
            <div className="pointer-events-none absolute -left-10 -top-10 h-48 w-48 rounded-full bg-white/15 blur-2xl" />
            <div className="pointer-events-none absolute -bottom-16 -right-8 h-56 w-56 rounded-full bg-sky-200/30 blur-3xl" />
            <div className="pointer-events-none absolute inset-0 opacity-30 [background-image:linear-gradient(rgba(255,255,255,0.18)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.18)_1px,transparent_1px)] [background-size:28px_28px]" />

            <div className="relative mx-auto max-w-2xl">
              <h2 className="text-balance text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl">
                Попробуйте FlyPing уже сегодня.
              </h2>
              <p className="mt-4 text-base text-sky-50/90 sm:text-lg">
                Откройте Telegram-бота и начните отслеживать цены на авиабилеты за пару минут.
              </p>
              <div className="mt-8 flex justify-center">
                <Button
                  href={siteConfig.telegramBotUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  size="lg"
                  className="bg-white text-brand-700 shadow-[0_12px_30px_rgba(15,23,42,0.18)] hover:bg-sky-50 hover:shadow-[0_16px_36px_rgba(15,23,42,0.22)]"
                >
                  <Send className="h-4 w-4" />
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
