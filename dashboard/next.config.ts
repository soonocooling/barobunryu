import path from "node:path";
import type { NextConfig } from "next";

// 카테고리 단일 출처(루트 keywords.json)를 빌드 시 import하므로 추적 루트를 저장소 루트로 둔다.
const repoRoot = path.join(__dirname, "..");

const nextConfig: NextConfig = {
  outputFileTracingRoot: repoRoot,
  turbopack: { root: repoRoot },
};

export default nextConfig;
