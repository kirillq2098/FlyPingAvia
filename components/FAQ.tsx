import { Accordion } from "@/components/ui/Accordion";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FAQ_ITEMS } from "@/lib/constants";

export function FAQ() {
  return (
    <section id="faq" className="relative scroll-mt-24 py-20 sm:py-24">
      <Container className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-start lg:gap-16">
        <Reveal>
          <SectionHeading
            align="left"
            eyebrow="FAQ"
            title="Частые вопросы"
            description="Коротко о том, как FlyPing помогает находить выгодные авиабилеты."
          />
        </Reveal>

        <Reveal delay={0.08}>
          <Accordion items={FAQ_ITEMS} />
        </Reveal>
      </Container>
    </section>
  );
}
