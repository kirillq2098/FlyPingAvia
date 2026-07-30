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
      "Вы выбираете маршрут в Telegram-боте. FlyPing отслеживает стоимость билетов и присылает сообщение, когда цена снижается.",
  },
  {
    id: "pay",
    question: "Нужно ли платить?",
    answer:
      "Базовый мониторинг доступен бесплатно. Расширенные возможности появятся позже как отдельные тарифы.",
  },
  {
    id: "frequency",
    question: "Как часто проверяются цены?",
    answer:
      "Проверки идут регулярно в течение суток, чтобы вовремя заметить снижение и отправить уведомление.",
  },
  {
    id: "countries",
    question: "Какие направления поддерживаются?",
    answer:
      "Популярные внутренние и международные маршруты. Список направлений постепенно расширяется.",
  },
  {
    id: "multiple",
    question: "Можно ли отслеживать несколько маршрутов?",
    answer:
      "Да. Добавьте несколько направлений и получайте отдельные уведомления по каждому.",
  },
];

export const DEMO_ROUTE = {
  origin: "Новосибирск",
  originCode: "OVB",
  destination: "Санкт-Петербург",
  destinationCode: "LED",
  dates: "12–19 сен",
  oldPrice: 18940,
  newPrice: 14620,
  drop: 4320,
} as const;

export const CHAT_ROUTE = {
  origin: "Новосибирск",
  destination: "Москва",
  dates: "12–19 сентября",
  drop: 2740,
} as const;

export function formatRub(value: number): string {
  return `${value.toLocaleString("ru-RU")} ₽`;
}
