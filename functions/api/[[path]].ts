import type { PagesFunction } from "@cloudflare/workers-types";
import { assetJson, jsonResponse, neonQuery, normalizeTopic, optionsResponse, windowDays, type Env } from "./_utils";

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request, env } = context;
  if (request.method === "OPTIONS") return optionsResponse(request, env);
  if (request.method !== "GET") return jsonResponse(request, env, { error: "method_not_allowed" }, 405);

  const path = normalizePath(context.params.path);
  const url = new URL(request.url);

  if (path[0] === "hotspots" && path[1] === "latest") {
    return withJsonFallback(request, env, "/data/hotspots/latest.json", async () => {
      return neonQuery(env, `
        select h.snapshot_hour, t.canonical_name as topic, h.paper_count, h.repo_count,
               h.github_star_delta, h.magnitude, h.severity_label, h.evidence_json
        from hourly_snapshots h join topics t on t.id = h.topic_id
        where h.snapshot_hour >= now() - interval '24 hours'
        order by h.magnitude desc, h.snapshot_hour desc
        limit 20
      `);
    });
  }

  if (path[0] === "reports" && path[1]) {
    return withJsonFallback(request, env, `/data/reports/${path[1]}.json`, async () => {
      return neonQuery(env, "select * from daily_reports where report_date = $1::date", [path[1]]);
    });
  }

  if (path[0] === "topics" && !path[1]) {
    return withJsonFallback(request, env, "/data/topics.json", async () => {
      return neonQuery(env, "select canonical_name, aliases, category, priority_weight, watchlist_level, enabled from topics where enabled = true order by canonical_name");
    });
  }

  if (path[0] === "topics" && path[1] && path[2] === "history") {
    const topic = normalizeTopic(path[1]);
    const days = windowDays(url.searchParams.get("window"));
    const rows = await neonQuery(env, `
      select h.snapshot_hour, t.canonical_name as topic, h.paper_count, h.repo_count,
             h.github_star_delta, h.magnitude, h.severity_label
      from hourly_snapshots h join topics t on t.id = h.topic_id
      where lower(t.canonical_name) = lower($1)
        and h.snapshot_hour >= now() - ($2 || ' days')::interval
      order by h.snapshot_hour
    `, [topic, days]);
    if (rows) return jsonResponse(request, env, { source: "neon", topic, window: `${days}d`, items: rows });
    return topicHistoryFromJson(request, env, topic, days);
  }

  if (path[0] === "topics" && path[1]) {
    const topic = normalizeTopic(path[1]);
    const rows = await neonQuery(env, "select * from topics where lower(canonical_name) = lower($1) limit 1", [topic]);
    if (rows && rows.length) return jsonResponse(request, env, { source: "neon", topic: rows[0] });
    return topicFromJson(request, env, topic);
  }

  if (path[0] === "github" && path[2] === "history") {
    const repo = decodeURIComponent(path[1] || "");
    const rows = await neonQuery(env, "select * from repo_snapshots where repo_full_name = $1 order by snapshot_at", [repo]);
    if (rows) return jsonResponse(request, env, { source: "neon", repo, items: rows });
    return withJsonFallback(request, env, "/data/snapshots/repo_snapshots.json");
  }

  if (path[0] === "institutions" && !path[1]) {
    return withJsonFallback(request, env, "/data/institutions.json", async () => {
      return neonQuery(env, "select * from institutions order by weight desc, canonical_name");
    });
  }

  if (path[0] === "institutions" && path[1]) {
    const name = normalizeTopic(path[1]);
    const rows = await neonQuery(env, "select * from institutions where lower(canonical_name) = lower($1) limit 1", [name]);
    if (rows && rows.length) return jsonResponse(request, env, { source: "neon", institution: rows[0] });
    return withJsonFallback(request, env, "/data/institutions.json");
  }

  if (path[0] === "watchlist") {
    return withJsonFallback(request, env, "/data/watchlist.json");
  }

  if (path[0] === "cooccurrence" && path[1] === "latest") {
    return withJsonFallback(request, env, "/data/graphs/cooccurrence/latest.json");
  }

  if (path[0] === "sources" && path[1] === "status") {
    const latest = await assetJson<Record<string, any>>(request, env, "/data/hotspots/latest.json");
    return jsonResponse(request, env, {
      source: "json",
      source_status: latest?.source_status || [],
      partial: latest?.partial ?? null
    });
  }

  return jsonResponse(request, env, { error: "not_found", path }, 404);
};

function normalizePath(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === "string") return value.split("/").filter(Boolean);
  return [];
}

async function withJsonFallback(
  request: Request,
  env: Env,
  assetPath: string,
  neonLoader?: () => Promise<unknown[] | null>
): Promise<Response> {
  if (neonLoader) {
    const rows = await neonLoader();
    if (rows) return jsonResponse(request, env, { source: "neon", items: rows });
  }
  const loaded = await assetJson(request, env, assetPath);
  if (loaded) return jsonResponse(request, env, { source: "json", data: loaded });
  return jsonResponse(request, env, { error: "not_found", assetPath }, 404);
}

async function topicHistoryFromJson(request: Request, env: Env, topic: string, days: number): Promise<Response> {
  const latest = await assetJson<Record<string, any>>(request, env, "/data/latest.json");
  const reportPath = latest?.report_json_path ? `/${latest.report_json_path}` : null;
  const report = reportPath ? await assetJson<Record<string, any>>(request, env, reportPath) : null;
  const chart = report?.trend_charts?.[topic]?.[`${days}d`] || [];
  return jsonResponse(request, env, { source: "json", topic, window: `${days}d`, items: chart });
}

async function topicFromJson(request: Request, env: Env, topic: string): Promise<Response> {
  const latest = await assetJson<Record<string, any>>(request, env, "/data/latest.json");
  const reportPath = latest?.report_json_path ? `/${latest.report_json_path}` : null;
  const report = reportPath ? await assetJson<Record<string, any>>(request, env, reportPath) : null;
  const signal = (report?.top_anomalies || []).find((item: any) => String(item.topic).toLowerCase() === topic.toLowerCase());
  if (signal) return jsonResponse(request, env, { source: "json", topic: signal });
  return jsonResponse(request, env, { error: "not_found", topic }, 404);
}
