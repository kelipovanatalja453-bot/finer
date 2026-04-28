import { NextResponse } from "next/server";

const UPSTREAM_URL = "http://127.0.0.1:8000/api/files/enrichment";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const entity = path.join("/");

  try {
    const res = await fetch(`${UPSTREAM_URL}/${encodeURIComponent(entity)}`, {
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error("API Proxy Error (GET /api/files/enrichment):", error);
    return NextResponse.json(
      { error: "Failed to connect to API backend" },
      { status: 502 }
    );
  }
}
