"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Container } from "@/components/ui/Container";
import { Reveal } from "@/components/ui/Reveal";
import { ROUTE, formatRub } from "@/lib/constants";

const HISTORY = [
  { time: "06:40", price: 18940, note: "старт отслеживания" },
  { time: "11:15", price: 18410, note: "незначительное изменение" },
  { time: "16:02", price: 16780, note: "снижение зафиксировано" },
  { time: "19:48", price: 14620, note: "уведомление отправлено" },
] as const;

export function InterfaceShowcase() {
  const reduceMotion = useReducedMotion();

  return (
    <section id="interface" className="scroll-mt-24 py-16 sm:py-24">
      <Container>
        <Reveal>
          <div className="mb-10 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <h2 className="max-w-2xl text-3xl font-semibold tracking-[-0.04em] text-ink sm:text-4xl lg:text-[2.75rem]">
              Экран маршрута, как на табло — только для цены.
            </h2>
            <p className="mono text-[11px] uppercase tracking-[0.16em] text-mute">
              live route panel
            </p>
          </div>
        </Reveal>

        <Reveal delay={0.06}>
          <div className="overflow-hidden rounded-[14px] border border-line bg-bg-elevated">
            <div className="grid border-b border-line lg:grid-cols-[1.1fr_0.9fr]">
              <div className="border-b border-line p-5 sm:p-8 lg:border-b-0 lg:border-r">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="mono text-[11px] uppercase tracking-[0.16em] text-mute">
                      active route
                    </p>
                    <div className="mt-5 flex items-end gap-4 sm:gap-6">
                      <div>
                        <p className="airport-code text-5xl text-ink sm:text-6xl">
                          {ROUTE.originCode}
                        </p>
                        <p className="mt-2 text-sm text-mute">{ROUTE.origin}</p>
                      </div>
                      <div className="mb-3 h-px w-16 bg-line-strong sm:w-24" />
                      <div>
                        <p className="airport-code text-5xl text-ink sm:text-6xl">
                          {ROUTE.destinationCode}
                        </p>
                        <p className="mt-2 text-sm text-mute">{ROUTE.destination}</p>
                      </div>
                    </div>
                  </div>
                  <p className="mono rounded-[4px] bg-gain-soft px-2 py-1 text-[11px] font-medium text-gain">
                    watching
                  </p>
                </div>

                <div className="mt-10 grid grid-cols-2 gap-x-6 gap-y-6 sm:grid-cols-4">
                  <Meta label="даты" value={ROUTE.dates} />
                  <Meta label="цель" value={formatRub(ROUTE.targetPrice)} />
                  <Meta label="проверка" value={ROUTE.checkEvery} />
                  <Meta label="последняя" value={ROUTE.checkedAt} />
                </div>
              </div>

              <div className="p-5 sm:p-8">
                <p className="mono text-[11px] uppercase tracking-[0.16em] text-mute">
                  current fare
                </p>
                <motion.p
                  className="mono mt-4 text-5xl font-semibold tracking-[-0.03em] text-ink sm:text-6xl"
                  initial={reduceMotion ? false : { opacity: 0.4 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6 }}
                >
                  {formatRub(ROUTE.newPrice)}
                </motion.p>
                <p className="mono mt-3 text-sm text-mute">
                  было {formatRub(ROUTE.oldPrice)} ·{" "}
                  <span className="text-gain">−{formatRub(ROUTE.drop)}</span>
                </p>

                <div className="mt-8 rounded-[8px] border border-line bg-bg p-4">
                  <p className="text-sm font-medium text-ink">Telegram</p>
                  <p className="mt-2 text-sm leading-6 text-mute">
                    Цена на {ROUTE.originCode}→{ROUTE.destinationCode} снизилась.
                    Открыть варианты.
                  </p>
                </div>
              </div>
            </div>

            <div className="p-5 sm:p-8">
              <div className="mb-4 flex items-center justify-between">
                <p className="mono text-[11px] uppercase tracking-[0.16em] text-mute">
                  price history
                </p>
                <p className="mono text-xs text-mute">UTC+7</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] text-left">
                  <thead>
                    <tr className="border-b border-line text-mute">
                      <th className="mono py-3 pr-4 text-[11px] font-medium uppercase tracking-[0.14em]">
                        time
                      </th>
                      <th className="mono py-3 pr-4 text-[11px] font-medium uppercase tracking-[0.14em]">
                        fare
                      </th>
                      <th className="mono py-3 text-[11px] font-medium uppercase tracking-[0.14em]">
                        status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {HISTORY.map((row) => (
                      <tr key={row.time} className="border-b border-line last:border-0">
                        <td className="mono py-3.5 pr-4 text-sm text-ink">{row.time}</td>
                        <td className="mono py-3.5 pr-4 text-sm text-ink">
                          {formatRub(row.price)}
                        </td>
                        <td className="py-3.5 text-sm text-mute">{row.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="mono text-[11px] uppercase tracking-[0.14em] text-mute">{label}</p>
      <p className="mono mt-2 text-sm font-medium text-ink">{value}</p>
    </div>
  );
}
