import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";

const PRINCIPLES = [
  {
    num: "01",
    title: "Укажите маршрут",
    text: "Город вылета, направление и даты. Одного сценария достаточно, чтобы начать мониторинг.",
  },
  {
    num: "02",
    title: "Продолжайте заниматься своими делами",
    text: "FlyPing проверяет цену без вашего участия. Отдельные вкладки и ручные сравнения больше не нужны.",
  },
  {
    num: "03",
    title: "Получите сообщение, когда цена снизится",
    text: "Уведомление приходит в Telegram — туда, где вы и так читаете сообщения.",
  },
] as const;

export function Principles() {
  return (
    <section id="principles" className="scroll-mt-24 py-16 sm:py-24">
      <Container>
        <Reveal>
          <div className="mb-12 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <h2 className="max-w-lg text-3xl font-semibold tracking-[-0.04em] text-ink sm:text-4xl">
              Три действия. Без лишнего интерфейса.
            </h2>
            <p className="mono text-[11px] uppercase tracking-[0.16em] text-mute">
              operating principles
            </p>
          </div>
        </Reveal>

        <div className="divide-y divide-line border-y border-line">
          {PRINCIPLES.map((item, index) => (
            <Reveal key={item.num} delay={index * 0.05}>
              <article className="grid gap-4 py-8 sm:grid-cols-12 sm:gap-8 sm:py-10">
                <p className="mono text-sm text-mute sm:col-span-2">{item.num}</p>
                <h3 className="text-2xl font-semibold tracking-[-0.035em] text-ink sm:col-span-4 sm:text-[1.75rem]">
                  {item.title}
                </h3>
                <p className="max-w-xl text-base leading-7 text-mute sm:col-span-6">
                  {item.text}
                </p>
              </article>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
