# FlyPing marketing site (Next.js App Router) — production image
# Build args bake NEXT_PUBLIC_* at compile time.

FROM node:20-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-bookworm-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_SITE_URL=https://flyping.ru
ARG NEXT_PUBLIC_TELEGRAM_BOT_URL=https://web.telegram.org/k/#@FlyPingAvia_Bot
ARG NEXT_PUBLIC_TELEGRAM_USERNAME=FlyPingAvia_Bot
ARG NEXT_PUBLIC_SUPPORT_EMAIL=Q2098@yandex.ru
ARG NEXT_PUBLIC_SUPPORT_TELEGRAM=https://t.me/Akulov_Kirill
ARG NEXT_PUBLIC_GA_ID=
ARG NEXT_PUBLIC_YANDEX_METRICA_ID=

ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_TELEGRAM_BOT_URL=$NEXT_PUBLIC_TELEGRAM_BOT_URL \
    NEXT_PUBLIC_TELEGRAM_USERNAME=$NEXT_PUBLIC_TELEGRAM_USERNAME \
    NEXT_PUBLIC_SUPPORT_EMAIL=$NEXT_PUBLIC_SUPPORT_EMAIL \
    NEXT_PUBLIC_SUPPORT_TELEGRAM=$NEXT_PUBLIC_SUPPORT_TELEGRAM \
    NEXT_PUBLIC_GA_ID=$NEXT_PUBLIC_GA_ID \
    NEXT_PUBLIC_YANDEX_METRICA_ID=$NEXT_PUBLIC_YANDEX_METRICA_ID \
    NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM node:20-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=127.0.0.1

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin siteuser

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER siteuser
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
