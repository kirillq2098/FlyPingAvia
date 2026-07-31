import { Accordion } from "@/components/ui/Accordion";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { FAQ_ITEMS } from "@/lib/constants";

export function FAQ() {
  return (
    <section id="faq" className="scroll-mt-24 border-t border-line py-16 sm:py-24">
      <Container className="grid gap-10 lg:grid-cols-12">
        <Reveal className="lg:col-span-4">
          <p className="mono text-[11px] uppercase tracking-[0.16em] text-mute">faq</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-[-0.04em] text-ink sm:text-4xl">
            Вопросы
          </h2>
        </Reveal>
        <Reveal delay={0.06} className="lg:col-span-8">
          <Accordion items={FAQ_ITEMS} />
        </Reveal>
      </Container>
    </section>
  );
}
