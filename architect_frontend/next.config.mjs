/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // Abstract Wiki Architect lives under this path on the main site
  // (matches Nginx + docs/hosting.md).
  basePath: process.env.NEXT_PUBLIC_ARCHITECT_BASE_PATH || "/abstract_wiki_architect",

  // Produce a self-contained build for easier Docker deployment.
  output: "standalone",

  experimental: {
    appDir: true,
  },

  // Public env defaults; can be overridden at build time.
  env: {
    // Base URL for the Architect HTTP API used by src/lib/api.ts, entityApi.ts, aiApi.ts.
    // In production, you typically point this at the backend service or an Nginx location
    // that proxies to it (e.g. "http://backend:8000" or "/abstract_wiki_architect_api").
    NEXT_PUBLIC_ARCHITECT_API_BASE_URL:
      process.env.NEXT_PUBLIC_ARCHITECT_API_BASE_URL || "http://localhost:8000",
  },
};

export default nextConfig;
