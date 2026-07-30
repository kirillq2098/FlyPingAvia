import Image from "next/image";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";

export function TravelEditorial() {
  return (
    <section className="border-y border-line bg-navy py-0 text-white">
      <Container className="grid lg:grid-cols-12">
        <Reveal className="relative min-h-[360px] lg:col-span-7 lg:min-h-[520px]">
          <Image
            src="/images/flyping-hero-travel.webp"
            alt="Путешествие: свет над облаками за иллюминатором"
            fill
            sizes="(max-width: 1024px) 100vw, 58vw"
            className="object-cover"
          />
        </Reveal>
        <Reveal
          delay={0.08}
          className="flex flex-col justify-between gap-10 px-0 py-12 lg:col-span-5 lg:px-10 lg:py-16"
        >
          <p className="mono text-[11px] uppercase tracking-[0.18em] text-navy-mute">
            travel desk
          </p>
          <div>
            <h2 className="max-w-[12ch] text-4xl font-semibold leading-[1.05] tracking-[-0.045em] sm:text-5xl">
              Вы планируете поездку.
              <br />
              FlyPing следит за ценой.
            </h2>
            <p className="mt-6 max-w-sm text-base leading-7 text-navy-mute">
              Пока вы выбираете даты и город, сервис продолжает проверки маршрута
              и сообщает только когда появляется смысл смотреть билет снова.
            </p>
          </div>
          <div className="flex items-center gap-6 border-t border-navy-line pt-6">
            <p className="airport-code text-3xl text-white">OVB</p>
            <span className="h-px flex-1 bg-navy-line" />
            <p className="airport-code text-3xl text-white">LED</p>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
