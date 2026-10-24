import type { NextConfig } from "next";

const apiBaseUrl = (process.env.API_BASE_URL || "http://127.0.0.1:5000")
  .replace(/\/+$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiBaseUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
