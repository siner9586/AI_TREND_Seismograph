import type { PagesFunction } from "@cloudflare/workers-types";
import { assetJson, jsonResponse, neonQuery, optionsResponse, type Env } from "./_utils";

export const onRequest: PagesFunction<Env> = async (context) => {
  if (context.request.method === "OPTIONS") return optionsResponse(context.request, context.env);
  const neonRows = await neonQuery(context.env, "select now() as now");
  const latest = await assetJson(context.request, context.env, "/data/latest.json");
  const hotspots = await assetJson(context.request, context.env, "/data/hotspots/latest.json");
  return jsonResponse(context.request, context.env, {
    ok: true,
    neon: Boolean(neonRows),
    jsonFallback: Boolean(latest || hotspots),
    checkedAt: new Date().toISOString()
  });
};
