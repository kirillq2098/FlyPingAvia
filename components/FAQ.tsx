import { Accordion } from "@/components/ui/Accordion";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { FAQ_ITEMS } from "@/lib/constants";

export function FAQ() {
  return (
    <section id="faq" className="scroll-mt-24 py-20 sm:py-24">
      <Container className="grid gap-10 lg:grid-cols-[0.85fr_1.15fr] lg:gap-16">
        <Reveal>
          <SectionHeading
            eyebrow="FAQ"
            title="Короткие ответы"
            description="Без лишнего. Только то, что важно перед запуском."
          />
        </Reveal>
        <Reveal delay={0.06}>
          <Accordion items={FAQ_ITEMS} />
        </Reveal>
      </Container>
    </section>
  );
}
