import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/SectionHeading";

export function Features() {
  return (
    <section id="features" className="scroll-mt-24 py-20 sm:py-24">
      <Container>
        <Reveal>
          <SectionHeading
            eyebrow="Почему это удобнее"
            title="Меньше рутины. Больше контроля над ценой."
          />
        </Reveal>

        <div className="mt-14 space-y-6">
          <Reveal>
            <article className="grid gap-8 rounded-[var(--radius-lg)] border border-line bg-surface-raised p-6 sm:p-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
              <div>
                <p className="text-sm font-medium text-muted">01</p>
                <h3 className="display mt-3 text-2xl leading-snug text-ink sm:text-3xl">
                  FlyPing проверяет цены круглосуточно
                </h3>
                <p className="mt-4 max-w-md text-base leading-7 text-muted">
                  Не нужно обновлять вкладки и сравнивать агрегаторы вручную.
                  Мониторинг идёт, пока вы заняты другими делами.
                </p>
              </div>
              <div className="rounded-[var(--radius)] border border-line bg-surface p-5">
                <div className="space-y-3">
                  {["06:12", "10:47", "15:03", "21:36"].map((time, index) => (
                    <div
                      key={time}
                      className="flex items-center justify-between border-b border-line pb-3 last:border-0 last:pb-0"
                    >
                      <span className="tabular text-sm text-muted">{time}</span>
                      <span className="text-sm text-ink">
                        {index === 3 ? "изменение найдено" : "проверка маршрута"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </article>
          </Reveal>

          <Reveal delay={0.05}>
            <article className="grid gap-8 rounded-[var(--radius-lg)] border border-line bg-surface p-6 sm:p-8 lg:grid-cols-[0.85fr_1.15fr] lg:items-center">
              <div className="order-2 rounded-[var(--radius)] border border-line bg-surface-raised p-5 lg:order-1">
                <div className="mx-auto max-w-xs rounded-[var(--radius)] border border-line bg-white p-4 shadow-[var(--shadow-soft)]">
                  <p className="text-xs text-muted">Telegram</p>
                  <p className="mt-3 text-sm font-medium text-ink">FlyPing</p>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    Цена на ваш маршрут снизилась. Открыть варианты.
                  </p>
                </div>
              </div>
              <div className="order-1 lg:order-2">
                <p className="text-sm font-medium text-muted">02</p>
                <h3 className="display mt-3 text-2xl leading-snug text-ink sm:text-3xl">
                  Сообщение приходит туда, где вы уже общаетесь
                </h3>
                <p className="mt-4 max-w-md text-base leading-7 text-muted">
                  Отдельное приложение не нужно. Уведомление появляется в Telegram —
                  рядом с привычными чатами.
                </p>
              </div>
            </article>
          </Reveal>

          <Reveal delay={0.08}>
            <article className="grid gap-8 overflow-hidden rounded-[var(--radius-lg)] border border-line bg-night p-6 text-white sm:p-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
              <div>
                <p className="text-sm font-medium text-night-muted">03</p>
                <h3 className="display mt-3 text-2xl leading-snug sm:text-3xl">
                  Не нужно держать открытыми сайты авиакомпаний
                </h3>
                <p className="mt-4 max-w-md text-base leading-7 text-night-muted">
                  Закройте вкладки. FlyPing продолжит следить за маршрутом и
                  сообщит, когда появится более выгодная цена.
                </p>
              </div>
              <div className="rounded-[var(--radius)] border border-night-line bg-night-elevated p-5">
                <p className="text-sm text-night-muted">Активные вкладки</p>
                <div className="mt-4 space-y-2">
                  <div className="h-9 rounded-[8px] bg-night-line" />
                  <div className="h-9 rounded-[8px] bg-night-line" />
                  <div className="flex h-9 items-center rounded-[8px] border border-dashed border-night-line px-3 text-sm text-night-muted">
                    закрыто
                  </div>
                </div>
              </div>
            </article>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
