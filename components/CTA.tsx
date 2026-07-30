import { Button } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { siteConfig } from "@/lib/site";

export function CTA() {
  return (
    <section id="cta" className="scroll-mt-24 bg-night py-20 sm:py-28">
      <Container>
        <Reveal>
          <div className="max-w-2xl">
            <h2 className="display text-balance text-3xl leading-[1.12] text-white sm:text-4xl lg:text-[3rem]">
              Не проверяйте цену каждый день.
            </h2>
            <p className="mt-4 text-lg text-night-muted">Поручите это FlyPing.</p>
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
