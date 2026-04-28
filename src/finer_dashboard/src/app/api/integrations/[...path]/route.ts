import { NextResponse } from "next/server";

const UPSTREAM_BASE = "http://127.0.0.1:8000/api/integrations";

export async function GET(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const proxyPath = path.join("/");
  const { searchParams } = new URL(request.url);
  const query = searchParams.toString();
  
  try {
    const res = await fetch(`${UPSTREAM_BASE}/${proxyPath}${query ? `?${query}` : ''}`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Upstream connection failed" }, { status: 502 });
  }
}

export async function POST(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const proxyPath = path.join("/");
  try {
    const body = await request.json();
    const res = await fetch(`${UPSTREAM_BASE}/${proxyPath}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Upstream connection failed" }, { status: 502 });
  }
}
