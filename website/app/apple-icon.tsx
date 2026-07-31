import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0B4DB8",
          borderRadius: 40,
        }}
      >
        <svg width="84" height="84" viewBox="0 0 22 22">
          <circle cx="4" cy="18" r="2.2" fill="white" />
          <path
            d="M5.8 16.4 C9 12.2, 13.2 7.4, 18.5 4.2"
            stroke="white"
            strokeWidth="1.8"
            strokeLinecap="round"
            fill="none"
          />
          <circle cx="18.5" cy="4.2" r="2.2" fill="white" />
          <circle
            cx="18.5"
            cy="4.2"
            r="4.4"
            stroke="white"
            strokeWidth="1"
            fill="none"
            opacity="0.4"
          />
        </svg>
      </div>
    ),
    size,
  );
}
