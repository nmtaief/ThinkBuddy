import { NextResponse } from "next/server";

export async function GET() {
  const buildInfo = {
    version: "0.1.0-pass9",
    build_timestamp: "2026-11-11T16:00:00+06:00",
    commit: "2d6671c02f8125b8cd86632897c26a444b7033c5",
    status: "production",
    framework: "next.js",
  };

  return NextResponse.json(buildInfo, {
    status: 200,
    headers: {
      "Cache-Control": "no-store, max-age=0",
    },
  });
}
