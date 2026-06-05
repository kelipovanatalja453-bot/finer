import { backendUrl, proxyGet } from "@/lib/api-proxy";

const UPSTREAM_URL = backendUrl("/api/stats");

export async function GET(request: Request) {
  return proxyGet(UPSTREAM_URL, request);
}
