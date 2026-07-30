import { Check, X } from "lucide-react";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { COMPARISON_ROWS } from "@/lib/constants";

export function Comparison() {
  return (
    <section id="comparison" className="relative scroll-mt-24 py-20 sm:py-24">
      <Container>
        <Reveal>
          <SectionHeading
            eyebrow="Сравнение"
            title="Обычный поиск VS FlyPing"
            description="Вместо ручной проверки сайтов — автоматический мониторинг и мгновенные уведомления."
          />
        </Reveal>

        <Reveal delay={0.1} className="mt-14 overflow-hidden rounded-[24px] border border-slate-200/80 bg-white/90 shadow-[0_20px_50px_rgba(15,23,42,0.06)] backdrop-blur">
          <div className="grid grid-cols-[1.2fr_0.7fr_1.2fr] gap-2 border-b border-slate-100 bg-slate-50/80 px-4 py-4 text-sm font-semibold text-slate-500 sm:px-8 sm:py-5 sm:text-base">
            <span>Обычный поиск</span>
            <span className="text-center">VS</span>
            <span className="text-right text-brand-600 sm:text-left">FlyPing</span>
          </div>

          <ul className="divide-y divide-slate-100">
            {COMPARISON_ROWS.map((row) => (
              <li
                key={row.id}
                className="grid grid-cols-1 gap-4 px-4 py-5 sm:grid-cols-[1.2fr_0.7fr_1.2fr] sm:items-center sm:gap-2 sm:px-8 sm:py-6"
              >
                <div className="flex items-start gap-3 text-slate-600">
                  <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-rose-50 text-rose-500 ring-1 ring-rose-100">
                    <X className="h-4 w-4" strokeWidth={2.5} />
                  </span>
                  <span className="text-sm sm:text-base">{row.traditional}</span>
                </div>

                <div className="hidden justify-center sm:flex">
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold tracking-wide text-slate-500">
                    VS
                  </span>
                </div>

                <div className="flex items-start gap-3 text-ink sm:justify-start">
                  <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 ring-1 ring-emerald-100">
                    <Check className="h-4 w-4" strokeWidth={2.5} />
                  </span>
                  <span className="text-sm font-medium sm:text-base">{row.flyping}</span>
                </div>
              </li>
            ))}
          </ul>
        </Reveal>
      </Container>
    </section>
  );
}
