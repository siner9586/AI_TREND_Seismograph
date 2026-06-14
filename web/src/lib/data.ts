import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import YAML from "yaml";

const dirname = path.dirname(fileURLToPath(import.meta.url));
export const repoRoot = path.resolve(dirname, "../../..");
export const dataRoot = path.join(repoRoot, "data");
export const configRoot = path.join(repoRoot, "config");

export function readJson<T>(relativePath: string, fallback: T): T {
  const fullPath = path.join(repoRoot, relativePath);
  if (!fs.existsSync(fullPath)) return fallback;
  return JSON.parse(fs.readFileSync(fullPath, "utf-8")) as T;
}

export function readYaml<T>(relativePath: string, fallback: T): T {
  const fullPath = path.join(repoRoot, relativePath);
  if (!fs.existsSync(fullPath)) return fallback;
  return YAML.parse(fs.readFileSync(fullPath, "utf-8")) as T;
}

export function latestBundle() {
  const latest = readJson<any>("data/latest.json", null);
  const hourly = readJson<any>("data/hotspots/latest.json", null);
  const history = readJson<any>("data/history/index.json", { reports: [] });
  const report = latest?.latest_report_date ? readJson<any>(`data/reports/${latest.latest_report_date}.json`, null) : null;
  return { latest, hourly, history, report };
}

export function formatBeijingHour(value?: string | null) {
  if (!value) return "未刷新";
  const raw = String(value).trim();
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2})(?::(\d{2}))?/);
  let date: Date;

  if (match) {
    const [, year, month, day, hour, minute = "00"] = match;
    date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute)));
  } else {
    date = new Date(raw);
  }

  if (Number.isNaN(date.getTime())) return raw;

  const beijing = new Date(date.getTime() + 8 * 60 * 60 * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");

  return `${beijing.getUTCFullYear()}-${pad(beijing.getUTCMonth() + 1)}-${pad(beijing.getUTCDate())} ${pad(beijing.getUTCHours())}:${pad(beijing.getUTCMinutes())} BJT`;
}

export function listReports() {
  const reportsDir = path.join(dataRoot, "reports");
  if (!fs.existsSync(reportsDir)) return [];
  return fs
    .readdirSync(reportsDir)
    .filter((name) => name.endsWith(".json"))
    .sort()
    .map((name) => readJson<any>(`data/reports/${name}`, null))
    .filter(Boolean);
}

export function listHotspots() {
  const root = path.join(dataRoot, "hotspots");
  if (!fs.existsSync(root)) return [];
  const rows: any[] = [];
  for (const date of fs.readdirSync(root).sort()) {
    const dateDir = path.join(root, date);
    if (!fs.statSync(dateDir).isDirectory()) continue;
    for (const file of fs.readdirSync(dateDir).sort()) {
      if (file.endsWith(".json")) rows.push(readJson<any>(`data/hotspots/${date}/${file}`, null));
    }
  }
  return rows.filter(Boolean);
}

export function taxonomy() {
  return readYaml<any>("config/trend_taxonomy.yml", { topics: [] }).topics || [];
}

export function institutionsConfig() {
  return readYaml<any>("config/institutions.yml", { institutions: [] }).institutions || [];
}

export function watchlistConfig() {
  return readYaml<any>("config/watchlist.yml", { watchlists: [] }).watchlists || [];
}

export function sourcesConfig() {
  return readYaml<any>("config/sources.yml", { sources: [] }).sources || [];
}

export function slugTopic(topic: string) {
  return encodeURIComponent(topic);
}

export function topicBySlug(slug: string) {
  return decodeURIComponent(slug);
}
