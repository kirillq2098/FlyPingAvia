import { ImageResponse } from "next/og";

export const size = {
  width: 180,
  height: 180,
};

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
          borderRadius: 40,
          background: "linear-gradient(135deg, #2563EB 0%, #38BDF8 100%)",
          color: "white",
          fontSize: 84,
          fontWeight: 700,
        }}
      >
        ✈
      </div>
    ),
    size,
  );
}
