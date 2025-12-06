/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // Abstract Wiki Architect lives under this path on the main site
  // (matches Nginx + docs/hosting.md).
  basePath:
    process.env.NEXT_PUBLIC_ARCHITECT_BASE_PATH ||
    "/abstract_wiki_architect",

  // Produce a self-contained build for easier Docker deployment.
  output: "standalone",

  // Public env defaults; can be overridden at build time.
  env: {
    NEXT_PUBLIC_ARCHITECT_API_BASE_URL:
      process.env.NEXT_PUBLIC_ARCHITECT_API_BASE_URL ||
      "http://localhost:8000",
  },
};

export default nextConfig;
