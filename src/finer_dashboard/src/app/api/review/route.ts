import { NextResponse } from "next/server";

const UPSTREAM_URL = "http://127.0.0.1:8000/api/review";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    
    const res = await fetch(UPSTREAM_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error("API Proxy Error (POST /api/review):", error);
    return NextResponse.json({ error: "Failed to connect to API backend" }, { status: 502 });
  }
}
