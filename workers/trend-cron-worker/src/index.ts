export interface Env {
  TREND_LOCKS: KVNamespace;
  GITHUB_TOKEN?: string;
  GITHUB_REPOSITORY?: string;
  PIPELINE_TRIGGER_URL?: string;
  PUBLIC_SITE_URL?: string;
}

const HOURLY_CRON = "8 * * * *";
const DAILY_CRON = "18 22 * * *";
const MAINTENANCE_CRON = "30 15 * * *";

export default {
  async scheduled(controller: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(handleScheduled(controller, env));
  },

  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return json({ ok: true, checkedAt: new Date().toISOString() });
    }
    if (url.pathname === "/run") {
      const mode = url.searchParams.get("mode") || "hourly";
      const force = url.searchParams.get("force") === "true";
      const now = new Date();
      const result = mode === "daily"
        ? await runDaily(env, now, force)
        : await runHourly(env, now, force);
      return json(result);
    }
    return json({ error: "not_found" }, 404);
  }
};

async function handleScheduled(controller: ScheduledController, env: Env): Promise<void> {
  const scheduledAt = new Date(controller.scheduledTime);
  if (controller.cron === HOURLY_CRON) {
    await runHourly(env, scheduledAt, false);
    return;
  }
  if (controller.cron === DAILY_CRON) {
    await runDaily(env, scheduledAt, false);
    return;
  }
  if (controller.cron === MAINTENANCE_CRON) {
    await runMaintenance(env, scheduledAt);
    return;
  }
  await runDailyCompensation(env, scheduledAt);
}

async function runHourly(env: Env, scheduledAt: Date, force: boolean): Promise<Record<string, unknown>> {
  const hour = isoHour(scheduledAt);
  const lockKey = `lock:hourly:${hour}`;
  return withLock(env, lockKey, 50 * 60, force, async () => {
    const result = await triggerPipeline(env, {
      workflow: "hourly-hotspots.yml",
      inputs: { hour, force: String(force), dry_run: "false", no_push: "false" }
    });
    await env.TREND_LOCKS.put(`state:hourly:${hour}`, JSON.stringify({ hour, result, updatedAt: new Date().toISOString() }), { expirationTtl: 86400 * 14 });
    return { mode: "hourly", hour, result };
  });
}

async function runDaily(env: Env, scheduledAt: Date, force: boolean): Promise<Record<string, unknown>> {
  const reportDate = beijingDate(scheduledAt);
  const lockKey = `lock:daily:${reportDate}`;
  return withLock(env, lockKey, 6 * 60 * 60, force, async () => {
    if (!force && await reportExists(env, reportDate)) {
      return { mode: "daily", reportDate, skipped: true, reason: "report already exists" };
    }
    const result = await triggerPipeline(env, {
      workflow: "daily-trend-seismograph.yml",
      inputs: { report_date: reportDate, lookback_hours: "72", force: String(force), dry_run: "false" }
    });
    await env.TREND_LOCKS.put(`state:daily:${reportDate}`, JSON.stringify({ reportDate, result, updatedAt: new Date().toISOString() }), { expirationTtl: 86400 * 90 });
    return { mode: "daily", reportDate, result };
  });
}

async function runDailyCompensation(env: Env, scheduledAt: Date): Promise<Record<string, unknown>> {
  const reportDate = beijingDate(scheduledAt);
  if (await reportExists(env, reportDate)) {
    return { mode: "daily-compensation", reportDate, skipped: true, reason: "report exists" };
  }
  return runDaily(env, scheduledAt, false);
}

async function runMaintenance(env: Env, scheduledAt: Date): Promise<Record<string, unknown>> {
  const date = beijingDate(scheduledAt);
  await env.TREND_LOCKS.put(`maintenance:${date}`, JSON.stringify({ date, checkedAt: new Date().toISOString() }), { expirationTtl: 86400 * 30 });
  return { mode: "maintenance", date, ok: true };
}

async function withLock(
  env: Env,
  key: string,
  ttlSeconds: number,
  force: boolean,
  fn: () => Promise<Record<string, unknown>>
): Promise<Record<string, unknown>> {
  if (!force) {
    const existing = await env.TREND_LOCKS.get(key);
    if (existing) return { skipped: true, reason: "lock exists", key };
  }
  await env.TREND_LOCKS.put(key, JSON.stringify({ lockedAt: new Date().toISOString() }), { expirationTtl: ttlSeconds });
  try {
    const result = await fn();
    await env.TREND_LOCKS.put(`${key}:done`, JSON.stringify({ doneAt: new Date().toISOString(), result }), { expirationTtl: 86400 * 14 });
    return result;
  } catch (error) {
    await enqueueRetry(env, key, error);
    return { ok: false, partial: true, key, error: error instanceof Error ? error.message : String(error) };
  }
}

async function triggerPipeline(env: Env, payload: { workflow: string; inputs: Record<string, string> }): Promise<Record<string, unknown>> {
  if (env.PIPELINE_TRIGGER_URL) {
    const response = await fetch(env.PIPELINE_TRIGGER_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    return { target: "pipeline_url", ok: response.ok, status: response.status, text: await response.text() };
  }
  if (!env.GITHUB_TOKEN || !env.GITHUB_REPOSITORY) {
    throw new Error("Set PIPELINE_TRIGGER_URL or GITHUB_TOKEN + GITHUB_REPOSITORY");
  }
  const response = await fetch(`https://api.github.com/repos/${env.GITHUB_REPOSITORY}/actions/workflows/${payload.workflow}/dispatches`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "User-Agent": "ai-trend-seismograph-worker"
    },
    body: JSON.stringify({ ref: "main", inputs: payload.inputs })
  });
  if (!response.ok) {
    throw new Error(`GitHub workflow dispatch failed: ${response.status} ${await response.text()}`);
  }
  return { target: "github_actions", workflow: payload.workflow, ok: true, status: response.status };
}

async function enqueueRetry(env: Env, key: string, error: unknown): Promise<void> {
  const retryKey = `retry:${new Date().toISOString()}:${key}`;
  await env.TREND_LOCKS.put(retryKey, JSON.stringify({
    key,
    error: error instanceof Error ? error.message : String(error),
    createdAt: new Date().toISOString()
  }), { expirationTtl: 86400 * 7 });
}

async function reportExists(env: Env, reportDate: string): Promise<boolean> {
  if (!env.PUBLIC_SITE_URL) return false;
  const response = await fetch(`${env.PUBLIC_SITE_URL.replace(/\/$/, "")}/data/reports/${reportDate}.json`, { method: "HEAD" });
  return response.ok;
}

function isoHour(date: Date): string {
  return date.toISOString().slice(0, 13);
}

function beijingDate(date: Date): string {
  return new Date(date.getTime() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" }
  });
}
