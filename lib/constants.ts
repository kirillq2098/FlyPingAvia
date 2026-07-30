import {
  Bell,
  Clock3,
  Coins,
  MessageCircle,
  Route,
  SearchX,
  type LucideIcon,
} from "lucide-react";

export type HowItWorksStep = {
  id: string;
  step: string;
  title: string;
  description: string;
};

export type FeatureItem = {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
};

export type ComparisonRow = {
  id: string;
  traditional: string;
  flyping: string;
};

export type FaqItem = {
  id: string;
  question: string;
  answer: string;
};

export type GalleryItem = {
  id: string;
  title: string;
  description: string;
};

export const HOW_IT_WORKS: HowItWorksStep[] = [
  {
    id: "route",
    step: "01",
    title: "Выберите маршрут",
    description:
      "Укажите направление и желаемые даты в Telegram-боте — займёт меньше минуты.",
  },
  {
    id: "monitor",
    step: "02",
    title: "FlyPing круглосуточно следит за ценой",
    description:
      "Сервис непрерывно мониторит стоимость билетов и сравнивает изменения в реальном времени.",
  },
  {
    id: "notify",
    step: "03",
    title: "Получите уведомление при снижении стоимости",
    description:
      "Как только цена падает, вы мгновенно получаете сообщение в Telegram.",
  },
];

export const FEATURES: FeatureItem[] = [
  {
    id: "24-7",
    title: "Отслеживание 24/7",
    description:
      "Цены мониторятся круглосуточно — даже когда вы спите или заняты.",
    icon: Clock3,
  },
  {
    id: "instant",
    title: "Моментальные уведомления",
    description:
      "Мгновенный сигнал в Telegram, как только стоимость становится выгоднее.",
    icon: Bell,
  },
  {
    id: "time",
    title: "Экономия времени",
    description:
      "Больше не нужно вручную обновлять страницы и сравнивать агрегаторы.",
    icon: SearchX,
  },
  {
    id: "money",
    title: "Экономия денег",
    description:
      "Ловите снижение цены раньше большинства путешественников.",
    icon: Coins,
  },
  {
    id: "telegram",
    title: "Работает через Telegram",
    description:
      "Привычный мессенджер вместо ещё одного приложения и аккаунта.",
    icon: MessageCircle,
  },
  {
    id: "routes",
    title: "Не нужно постоянно проверять сайты",
    description:
      "Настройте маршруты один раз — дальше FlyPing делает работу за вас.",
    icon: Route,
  },
];

export const COMPARISON_ROWS: ComparisonRow[] = [
  {
    id: "check",
    traditional: "Постоянно проверять сайты",
    flyping: "Автоматический мониторинг",
  },
  {
    id: "miss",
    traditional: "Можно пропустить скидку",
    flyping: "Моментальное уведомление",
  },
  {
    id: "time",
    traditional: "Тратится время",
    flyping: "Работает автоматически",
  },
];

export const FAQ_ITEMS: FaqItem[] = [
  {
    id: "how",
    question: "Как работает FlyPing?",
    answer:
      "Вы выбираете маршрут в Telegram-боте, а FlyPing автоматически отслеживает стоимость авиабилетов и присылает уведомление, когда цена снижается.",
  },
  {
    id: "pay",
    question: "Нужно ли платить?",
    answer:
      "Базовый функционал доступен бесплатно. В будущем появятся расширенные тарифы с дополнительными возможностями мониторинга.",
  },
  {
    id: "frequency",
    question: "Как часто проверяются цены?",
    answer:
      "Система проверяет цены регулярно в течение суток, чтобы вовремя заметить снижение и отправить уведомление.",
  },
  {
    id: "countries",
    question: "Какие страны поддерживаются?",
    answer:
      "FlyPing ориентирован на популярные международные и внутренние направления. Список маршрутов постоянно расширяется.",
  },
  {
    id: "multiple",
    question: "Можно ли отслеживать несколько маршрутов?",
    answer:
      "Да, вы можете добавить несколько направлений и получать отдельные уведомления по каждому из них.",
  },
];

export const GALLERY_ITEMS: GalleryItem[] = [
  {
    id: "bot",
    title: "Диалог с ботом",
    description: "Простой сценарий настройки маршрута в Telegram.",
  },
  {
    id: "alert",
    title: "Уведомление о цене",
    description: "Мгновенный алерт, когда билет становится дешевле.",
  },
  {
    id: "routes",
    title: "Список маршрутов",
    description: "Все отслеживания — в одном удобном месте.",
  },
];
