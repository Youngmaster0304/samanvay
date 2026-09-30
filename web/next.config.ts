import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Emits .next/standalone, which is what the production image serves.
  output: "standalone",
  // Scope Turbopack to this package so a stray lockfile higher up the tree is
  // not treated as part of this project.
  turbopack: { root: projectRoot },
};

export default nextConfig;
