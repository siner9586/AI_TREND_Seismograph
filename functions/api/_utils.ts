import { neon } from "@neondatabase/serverless";

export interface Env {
  DATABASE_URL?: string;
  NEON_DATABASE_URL?: string;
  PUBLIC_SITE_URL?: string;
  CORS_ALLOW_ORIGINS?: string;
  ASSETS?: { fetch(request: Request): Promise<Response> };
}

export function corsHeaders(request: Request, env: Env): HeadersInit {
  const origin = request.headers.get("Origin") || "";
  const configured = (env.CORS_ALLOW_ORIGINS || env.PUBLIC_SITE_URL || "*")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const allowed = configured.includes("*") || configured.includes(origin) ? origin || "*" : configured[0] || "*";
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Vary": "Origin"
  };
}

export function jsonResponse(request: Request, env: Env, body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders(request, env)
    }
  });
}

export function optionsResponse(request: Request, env: Env): Response {
  return new Response(null, { status: 204, headers: corsHeaders(request, env) });
}

export async function neonQuery<T = Record<string, unknown>>(env: Env, sqlText: string, params: unknown[] = []): Promise<T[] | null> {
  const url = env.DATABASE_URL || env.NEON_DATABASE_URL;
  if (!url) return null;
  try {
    const sql = neon(url);
    return (await sql.query(sqlText, params)) as T[];
  } catch (error) {
    console.warn("Neon query failed; falling back to JSON", error);
    return null;
  }
}

export async function assetJson<T = unknown>(request: Request, env: Env, path: string): Promise<T | null> {
  const url = new URL(request.url);
  const assetUrl = new URL(path, `${url.protocol}//${url.host}`);
  let response: Response | null = null;
  if (env.ASSETS) {
    response = await env.ASSETS.fetch(new Request(assetUrl.toString(), request));
  } else {
    response = await fetch(assetUrl.toString());
  }
  if (!response.ok) return null;
  return (await response.json()) as T;
}

export function normalizeTopic(value: string): string {
  return decodeURIComponent(value).replace(/-/g, " ").trim();
}

export function windowDays(value: string | null): number {
  if (value === "90d") return 90;
  if (value === "180d") return 180;
  return 30;
}
