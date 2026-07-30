import { ImageResponse } from "next/og";
import { siteConfig } from "@/lib/site";

export const alt = siteConfig.tagline;
export const size = { width: 1200, height: 630 };
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
          padding: 64,
          background: "#F7F8FA",
          color: "#0A0B0D",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>FlyPing</div>
          <div style={{ fontSize: 48, fontWeight: 700, letterSpacing: 2 }}>OVB → LED</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 64, fontWeight: 700, lineHeight: 1.05, maxWidth: 900 }}>
            Билет подешевел. FlyPing уже сообщил.
          </div>
          <div style={{ fontSize: 28, color: "#5C6570", maxWidth: 760 }}>
            Мониторинг маршрута и уведомление в Telegram при снижении цены.
          </div>
        </div>
        <div style={{ display: "flex", gap: 28, fontSize: 28, fontWeight: 600 }}>
          <div style={{ color: "#5C6570", textDecoration: "line-through" }}>18 940 ₽</div>
          <div>14 620 ₽</div>
          <div style={{ color: "#0E9F6E" }}>−4 320 ₽</div>
        </div>
      </div>
    ),
    size,
  );
}
