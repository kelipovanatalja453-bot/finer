import { NextResponse } from "next/server";
import { backendUrl } from "@/lib/api-proxy";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const path = searchParams.get("path");

  if (!path) {
    return new NextResponse("Missing path", { status: 400 });
  }

  try {
    const res = await fetch(backendUrl(`/api/streams/download?path=${encodeURIComponent(path)}`));
    
    // We stream the exact response back to Next.js Client
    const headers = new Headers(res.headers);
    return new NextResponse(res.body, {
      status: res.status,
      headers: headers
    });
  } catch {
    return new NextResponse("Failed to proxy stream", { status: 502 });
  }
}
