import type { NextConfig } from "next";

// The FastAPI backend. In production set BACKEND_URL to its public URL.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Same-origin proxy: the browser only talks to this site, so the backend's HTTP-only
  // session cookie works without any cross-origin configuration.
  async rewrites() {
    return [
      { source: "/v1/:path*", destination: `${BACKEND_URL}/v1/:path*` },
      { source: "/api-reference", destination: `${BACKEND_URL}/docs` },
      { source: "/openapi.json", destination: `${BACKEND_URL}/openapi.json` },
    ];
  },
};

export default nextConfig;
