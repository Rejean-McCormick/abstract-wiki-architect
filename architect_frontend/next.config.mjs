/** @type {import('next').NextConfig} */

const ARCHITECT_BASE_PATH =
  process.env.NEXT_PUBLIC_ARCHITECT_BASE_PATH || "/semantik_architect";

const basePathRaw = ARCHITECT_BASE_PATH || "/semantik_architect";
const basePath = basePathRaw.startsWith("/") ? basePathRaw : `/${basePathRaw}`;

const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // Semantik Architect lives under this path on the main site
  basePath,

  // Produce a self-contained build for easier Docker deployment.
  output: "standalone",
};

export default nextConfig;