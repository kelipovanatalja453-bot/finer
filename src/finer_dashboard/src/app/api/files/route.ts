import { NextResponse } from "next/server";

const UPSTREAM_URL = "http://127.0.0.1:8000/api/files";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);

  try {
    const url = new URL(UPSTREAM_URL);
    // Forward all query parameters
    searchParams.forEach((value, key) => {
      url.searchParams.set(key, value);
    });
    // Ensure tier defaults to F1 if not provided
    if (!url.searchParams.has("tier")) {
      url.searchParams.set("tier", "F1");
    }
    const res = await fetch(url.toString(), { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error("API Proxy Error (GET /api/files):", error);
    return NextResponse.json({ error: "Failed to connect to API backend" }, { status: 502 });
  }
}

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const res = await fetch(UPSTREAM_URL, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error("API Proxy Error (POST /api/files):", error);
    return NextResponse.json({ error: "Failed to connect to API backend" }, { status: 502 });
  }
}
