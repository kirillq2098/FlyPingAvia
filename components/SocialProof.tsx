import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";

const METRICS = [
  { value: "24/7", label: "мониторинг" },
  { value: "1 минута", label: "настройка" },
  { value: "Telegram", label: "все уведомления" },
] as const;

export function SocialProof() {
  return (
    <section className="border-y border-line bg-surface py-10 sm:py-12">
      <Container className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
        <Reveal>
          <p className="display max-w-md text-2xl leading-snug text-ink sm:text-[1.75rem]">
            FlyPing проверяет цены вместо вас
          </p>
        </Reveal>
        <Reveal delay={0.06}>
          <dl className="grid grid-cols-1 gap-6 sm:grid-cols-3 sm:gap-10">
            {METRICS.map((metric) => (
              <div key={metric.value}>
                <dt className="tabular text-xl font-semibold tracking-[-0.03em] text-ink">
                  {metric.value}
                </dt>
                <dd className="mt-1 text-sm text-muted">{metric.label}</dd>
              </div>
            ))}
          </dl>
        </Reveal>
      </Container>
    </section>
  );
}
