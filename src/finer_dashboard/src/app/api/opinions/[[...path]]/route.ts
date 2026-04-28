import { NextResponse } from "next/server";

const UPSTREAM_URL = "http://127.0.0.1:8000/api/opinions";

export async function GET(request: Request) {
  const { searchParams, pathname } = new URL(request.url);

  // 提取路径参数
  const path = pathname.replace("/api/opinions", "");
  const queryString = searchParams.toString();
  const targetUrl = `${UPSTREAM_URL}${path}${queryString ? `?${queryString}` : ""}`;

  try {
    const res = await fetch(targetUrl, {
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!res.ok) {
      const errorText = await res.text();
      console.error(`API Proxy Error (GET ${targetUrl}):`, errorText);
      return NextResponse.json(
        { error: `Backend error: ${res.status}`, details: errorText },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error(`API Proxy Error (GET ${targetUrl}):`, error);
    return NextResponse.json(
      { error: "Failed to connect to API backend" },
      { status: 502 }
    );
  }
}

export async function POST(request: Request) {
  const { pathname } = new URL(request.url);
  const path = pathname.replace("/api/opinions", "");
  const targetUrl = `${UPSTREAM_URL}${path}`;

  try {
    const body = await request.json();

    const res = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error(`API Proxy Error (POST ${targetUrl}):`, error);
    return NextResponse.json(
      { error: "Failed to connect to API backend" },
      { status: 502 }
    );
  }
}
