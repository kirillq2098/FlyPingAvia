import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow preview tunnels / cloud port forwards in development
  allowedDevOrigins: [
    "*.loca.lt",
    "*.localtunnel.me",
    "*.ngrok-free.app",
    "*.ngrok.io",
    "localhost",
    "127.0.0.1",
  ],
};

export default nextConfig;
