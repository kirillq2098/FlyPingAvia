/**
 * Feature flags and future product surfaces.
 * Keep routes/modules additive so marketing, auth, billing and admin
 * can grow without rewriting the landing foundation.
 */
export const featureFlags = {
  dashboard: false,
  telegramAuth: false,
  paidSubscription: false,
  notificationHistory: false,
  blog: false,
  pricingPage: false,
  adminPanel: false,
} as const;

export type FeatureFlag = keyof typeof featureFlags;

/**
 * Planned App Router segments (not implemented yet):
 * - app/(auth)/login
 * - app/(dashboard)/dashboard
 * - app/(dashboard)/notifications
 * - app/pricing
 * - app/blog
 * - app/admin
 */
export const plannedRoutes = [
  "/dashboard",
  "/login",
  "/pricing",
  "/blog",
  "/admin",
  "/notifications",
] as const;
