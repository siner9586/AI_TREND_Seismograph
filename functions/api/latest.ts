import type { PagesFunction } from "@cloudflare/workers-types";
import { assetJson, jsonResponse, neonQuery, optionsResponse, type Env } from "./_utils";

export const onRequest: PagesFunction<Env> = async (context) => {
  if (context.request.method === "OPTIONS") return optionsResponse(context.request, context.env);
  const rows = await neonQuery(context.env, `
    select report_date, report_json_path, report_md_path, max_magnitude, generated_at, status
    from daily_reports
    order by report_date desc
    limit 1
  `);
  if (rows && rows.length) {
    return jsonResponse(context.request, context.env, { source: "neon", latest: rows[0] });
  }
  const latest = await assetJson(context.request, context.env, "/data/latest.json");
  return jsonResponse(context.request, context.env, { source: "json", latest: latest || null });
};
