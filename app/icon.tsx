import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 8,
          background: "#1A3F8B",
          color: "white",
          fontSize: 12,
          fontWeight: 700,
          fontFamily: "sans-serif",
        }}
      >
        FP
      </div>
    ),
    size,
  );
}
