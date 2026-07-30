import { ImageResponse } from "next/og";
import { siteConfig } from "@/lib/site";

export const alt = `${siteConfig.name} — мониторинг цен на авиабилеты`;
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 72,
          background: "#F2F0EB",
          color: "#1C1B19",
          fontFamily: "serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 10,
              background: "#1A3F8B",
              color: "white",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 18,
              fontWeight: 700,
              fontFamily: "sans-serif",
            }}
          >
            FP
          </div>
          <div style={{ fontSize: 28, fontFamily: "sans-serif", fontWeight: 600 }}>
            {siteConfig.name}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={{ fontSize: 58, lineHeight: 1.1, maxWidth: 920 }}>
            Цена на билет изменилась. Вы узнаете первым.
          </div>
          <div
            style={{
              fontSize: 26,
              color: "#6B6860",
              maxWidth: 780,
              lineHeight: 1.35,
              fontFamily: "sans-serif",
            }}
          >
            Мониторинг маршрута и уведомления о снижении цены в Telegram.
          </div>
        </div>
      </div>
    ),
    size,
  );
}
