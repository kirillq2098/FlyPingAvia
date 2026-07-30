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
          background:
            "linear-gradient(145deg, #F8FAFC 0%, #EFF6FF 45%, #E0F2FE 100%)",
          color: "#0F172A",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 18,
          }}
        >
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 20,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "linear-gradient(135deg, #2563EB 0%, #38BDF8 100%)",
              color: "white",
              fontSize: 32,
            }}
          >
            ✈
          </div>
          <div style={{ fontSize: 36, fontWeight: 700 }}>{siteConfig.name}</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div
            style={{
              fontSize: 64,
              fontWeight: 700,
              lineHeight: 1.1,
              maxWidth: 980,
            }}
          >
            Находите дешёвые авиабилеты первыми.
          </div>
          <div
            style={{
              fontSize: 28,
              color: "#475569",
              maxWidth: 880,
              lineHeight: 1.4,
            }}
          >
            Автоматический мониторинг цен и мгновенные уведомления в Telegram.
          </div>
        </div>
      </div>
    ),
    size,
  );
}
