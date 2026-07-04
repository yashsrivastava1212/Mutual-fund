#!/usr/bin/env node
/**
 * Generate ui/vercel.json from RAILWAY_API_URL (set in Vercel project env).
 * Build command on Vercel: node generate-vercel-config.mjs
 */
import { writeFileSync } from "fs";

const apiUrl = (process.env.RAILWAY_API_URL || "https://YOUR-RAILWAY-URL.up.railway.app").replace(
  /\/$/,
  "",
);

const config = {
  rewrites: [
    {
      source: "/api/:path*",
      destination: `${apiUrl}/api/:path*`,
    },
  ],
  headers: [
    {
      source: "/(.*)",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
      ],
    },
  ],
};

writeFileSync("vercel.json", `${JSON.stringify(config, null, 2)}\n`);
console.log(`Wrote vercel.json with API destination: ${apiUrl}`);
