import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  eslint: {
    // Don’t fail the production build on ESLint errors
    ignoreDuringBuilds: true,
  },
  typescript: {
    // Allow production builds to succeed even with type errors.
    ignoreBuildErrors: true,
  },
  experimental: {},
};

export default nextConfig;
