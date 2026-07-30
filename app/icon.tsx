import { ImageResponse } from "next/og";

export const size = {
  width: 32,
  height: 32,
};

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
          borderRadius: 10,
          background: "linear-gradient(135deg, #2563EB 0%, #38BDF8 100%)",
          color: "white",
          fontSize: 18,
          fontWeight: 700,
        }}
      >
        ✈
      </div>
    ),
    size,
  );
}
