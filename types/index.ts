/**
 * Shared domain types for upcoming product modules.
 * Landing currently uses content types from `lib/constants.ts`.
 */

export type UserId = string;

export type TelegramAuthPayload = {
  id: number;
  username?: string;
  firstName?: string;
  photoUrl?: string;
  authDate: number;
  hash: string;
};

export type SubscriptionPlan = "free" | "pro" | "business";

export type Subscription = {
  userId: UserId;
  plan: SubscriptionPlan;
  status: "active" | "canceled" | "past_due" | "trialing";
  renewsAt?: string;
};

export type TrackedRoute = {
  id: string;
  userId: UserId;
  origin: string;
  destination: string;
  departDate?: string;
  returnDate?: string;
  targetPrice?: number;
  currency: string;
  active: boolean;
};

export type PriceAlert = {
  id: string;
  routeId: string;
  userId: UserId;
  oldPrice: number;
  newPrice: number;
  currency: string;
  createdAt: string;
  readAt?: string;
};

export type BlogPost = {
  slug: string;
  title: string;
  excerpt: string;
  publishedAt: string;
};
