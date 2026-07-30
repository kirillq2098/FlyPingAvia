export type FaqItem = {
  id: string;
  question: string;
  answer: string;
};

export const FAQ_ITEMS: FaqItem[] = [
  {
    id: "how",
    question: "Как работает FlyPing?",
    answer:
      "Вы указываете маршрут в Telegram. FlyPing отслеживает цену и присылает сообщение, когда билет становится дешевле.",
  },
  {
    id: "pay",
    question: "Нужно ли платить?",
    answer:
      "Базовый мониторинг доступен бесплатно. Расширенные возможности появятся позже.",
  },
  {
    id: "frequency",
    question: "Как часто проверяется цена?",
    answer:
      "Проверки идут регулярно в течение суток, чтобы вовремя заметить снижение.",
  },
  {
    id: "multiple",
    question: "Можно ли следить за несколькими маршрутами?",
    answer:
      "Да. Добавьте несколько направлений и получайте отдельные уведомления.",
  },
];

export const ROUTE = {
  origin: "Новосибирск",
  originCode: "OVB",
  destination: "Санкт-Петербург",
  destinationCode: "LED",
  dates: "12–19 сен",
  departLocal: "08:40",
  checkedAt: "19:48",
  oldPrice: 18940,
  newPrice: 14620,
  drop: 4320,
  targetPrice: 15000,
  checkEvery: "каждую минуту",
} as const;

export function formatRub(value: number): string {
  return `${value.toLocaleString("ru-RU")}\u00A0₽`;
}
