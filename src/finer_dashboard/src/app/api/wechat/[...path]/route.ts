import { NextResponse } from "next/server";
import { backendUrl, safeJsonResponse } from "@/lib/api-proxy";

const UPSTREAM_BASE = backendUrl("/api/wechat");

/**
 * Forward a request to the WeChat backend.
 *
 * Security: we do NOT pass the browser's headers through wholesale (that would
 * leak the dashboard's cookies / Authorization header to the backend). Only a
 * minimal allowlist is forwarded. The backend authenticates the exporter via
 * its own server-side config, not via browser credentials.
 */
async function proxyRequest(
  request: Request,
  method: string,
  path: string[],
): Promise<NextResponse> {
  const proxyPath = path.join("/");
  const { searchParams } = new URL(request.url);
  const query = searchParams.toString();
  const url = `${UPSTREAM_BASE}/${proxyPath}${query ? `?${query}` : ""}`;

  const fetchInit: RequestInit = {
    method,
    cache: "no-store",
  };

  if (method === "POST" || method === "PUT") {
    let body: string | undefined;
    const contentType = request.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      try {
        const parsed = await request.json();
        body = JSON.stringify(parsed);
      } catch {
        // Empty body or invalid JSON — send no body.
      }
    } else {
      const text = await request.text().catch(() => "");
      if (text) body = text;
    }
    if (body) {
      fetchInit.body = body;
      fetchInit.headers = { "Content-Type": "application/json" };
    }
  }

  try {
    const res = await fetch(url, fetchInit);
    const { data, status } = await safeJsonResponse(res);
    return NextResponse.json(data, { status });
  } catch (error) {
    console.error(`API Proxy Error (${method} /api/wechat/${proxyPath}):`, error);
    return NextResponse.json(
      { ok: false, error: { code: "PROXY_ERROR", message: "Failed to connect to API backend" } },
      { status: 502 },
    );
  }
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest(request, "GET", path);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest(request, "POST", path);
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest(request, "DELETE", path);
}
