import { NextResponse } from "next/server";
import { backendUrl, safeJsonResponse } from "@/lib/api-proxy";

const UPSTREAM_URL = backendUrl("/api/files/enrichment");

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
    const { data, status } = await safeJsonResponse(res);
    return NextResponse.json(data, { status });
  } catch (error) {
    console.error("API Proxy Error (GET /api/files/enrichment):", error);
    return NextResponse.json(
      { ok: false, error: { code: "PROXY_ERROR", message: "Failed to connect to API backend" } },
      { status: 502 },
    );
  }
}
