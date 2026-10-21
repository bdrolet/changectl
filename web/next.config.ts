import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    // Uploads are capped at 25 MB; 27 MB leaves room for the multipart
    // boundaries and field metadata. The server-action limit defaults to
    // 1 MB and the proxy's buffered-body limit to 10 MB, and both apply to
    // /changes/* uploads.
    serverActions: { bodySizeLimit: "27mb" },
    proxyClientMaxBodySize: "27mb",
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
