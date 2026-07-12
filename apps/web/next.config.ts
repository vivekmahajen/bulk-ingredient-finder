import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// Proxy /api/* to the backend so the browser always talks to the web app's own
// origin. This keeps the auth cookies first-party (same registrable domain as
// the site), which a split web/API deployment (Vercel + Railway) otherwise
// breaks. Set NEXT_PUBLIC_API_URL to the API's base URL (no trailing slash).
const apiTarget = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@rasoi/shared"],
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiTarget}/api/:path*` }];
  },
};

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

export default withNextIntl(nextConfig);
