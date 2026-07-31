import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  compress: true,
  images: {
    formats: ["image/avif", "image/webp"],
  },
  // Allow preview tunnels / cloud port forwards in development
  allowedDevOrigins: [
    "*.loca.lt",
    "*.localtunnel.me",
    "*.ngrok-free.app",
    "*.ngrok.io",
    "*.trycloudflare.com",
    "localhost",
    "127.0.0.1",
  ],
};

export default nextConfig;
