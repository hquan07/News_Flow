import type { NextConfig } from "next";

const apiProxyTarget =
  process.env.API_PROXY_TARGET ??
  (process.env.NODE_ENV === "development"
    ? "http://127.0.0.1:8001"
    : "http://api:8000");

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    useTypeScriptCli: true,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
