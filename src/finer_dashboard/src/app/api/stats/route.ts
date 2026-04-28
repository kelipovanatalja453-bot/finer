import { NextResponse } from "next/server";

const UPSTREAM_URL = "http://127.0.0.1:8000/api/stats";

export async function GET() {
  try {
    const res = await fetch(UPSTREAM_URL, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error("API Proxy Error (GET /api/stats):", error);
    return NextResponse.json({ error: "Failed to connect to API backend" }, { status: 502 });
  }
}
