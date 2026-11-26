import type { NextConfig } from "next";

/**
 * The browser only ever talks to this origin. `/api/v1/*` is proxied server-side to the
 * FastAPI service (API_URL), so no CORS is needed and the API host is never hard-coded
 * in client bundles.
 */
const API_URL = (process.env.API_URL || "http://localhost:8000").replace(/\/$/, "");
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";

const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'" + (process.env.NODE_ENV === "development" ? " 'unsafe-eval'" : ""),
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: ${SUPABASE_URL}`,
  `connect-src 'self' ${SUPABASE_URL} ${SUPABASE_URL.replace("https://", "wss://")}`,
  "font-src 'self' data:",
  "frame-ancestors 'self' https://*.e2b.app",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  allowedDevOrigins: ["*.e2b.app"],
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${API_URL}/api/v1/:path*` },
      // Local mode stores images on the API's filesystem; this keeps every browser
      // request same-origin (no localhost:8000 leaking into the page, works on previews).
      { source: "/files/:path*", destination: `${API_URL}/files/:path*` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
