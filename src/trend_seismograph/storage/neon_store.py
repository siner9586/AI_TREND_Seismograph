from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class NeonWriteResult:
    enabled: bool
    ok: bool
    message: str


class NeonStore:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")

    @property
    def enabled(self) -> bool:
        return bool(self.database_url)

    def _connect(self):
        import psycopg

        if not self.database_url:
            raise RuntimeError("DATABASE_URL/NEON_DATABASE_URL is not configured")
        return psycopg.connect(self.database_url)

    def sync(self, raw_items: list[dict[str, Any]], hourly: dict[str, Any] | None = None, report: dict[str, Any] | None = None) -> NeonWriteResult:
        if not self.enabled:
            return NeonWriteResult(False, False, "Neon not configured; file storage used")
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    for item in raw_items:
                        cur.execute(
                            """
                            insert into raw_items (
                              source_type, source_name, external_id, title, abstract_or_description,
                              authors, institutions, url, published_at, fetched_at, raw_json,
                              content_hash, dedupe_key
                            )
                            values (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s::jsonb,%s,%s)
                            on conflict (dedupe_key) do update set
                              fetched_at = excluded.fetched_at,
                              raw_json = excluded.raw_json,
                              updated_at = now()
                            """,
                            (
                                item.get("source_type"),
                                item.get("source_name"),
                                item.get("external_id"),
                                item.get("title"),
                                item.get("abstract_or_description"),
                                item.get("authors_json", "[]"),
                                item.get("institutions_json", "[]"),
                                item.get("url"),
                                item.get("published_at"),
                                item.get("fetched_at"),
                                item.get("raw_json_string", "{}"),
                                item.get("content_hash"),
                                item.get("dedupe_key"),
                            ),
                        )
                    if hourly:
                        for hotspot in hourly.get("top_hotspots", []):
                            cur.execute(
                                """
                                insert into hourly_snapshots (
                                  snapshot_hour, topic_id, paper_count, repo_count, github_star_delta,
                                  method_mentions, dataset_mentions, institution_mentions, burst_score,
                                  magnitude, severity_label, evidence_json
                                )
                                values (
                                  %s,
                                  (select id from topics where canonical_name = %s limit 1),
                                  %s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb
                                )
                                on conflict (snapshot_hour, topic_id) do update set
                                  paper_count = excluded.paper_count,
                                  repo_count = excluded.repo_count,
                                  github_star_delta = excluded.github_star_delta,
                                  burst_score = excluded.burst_score,
                                  magnitude = excluded.magnitude,
                                  severity_label = excluded.severity_label,
                                  evidence_json = excluded.evidence_json
                                """,
                                (
                                    hourly.get("snapshot_hour"),
                                    hotspot.get("topic"),
                                    hotspot.get("metrics", {}).get("paper_count", 0),
                                    hotspot.get("metrics", {}).get("repo_count", 0),
                                    hotspot.get("metrics", {}).get("github_star_delta", 0),
                                    hotspot.get("metrics", {}).get("method_mentions", 0),
                                    hotspot.get("metrics", {}).get("dataset_mentions", 0),
                                    hotspot.get("metrics", {}).get("institution_mentions", 0),
                                    hotspot.get("metrics", {}).get("burst_score", 0),
                                    hotspot.get("magnitude", 0),
                                    hotspot.get("severity_label"),
                                    hotspot.get("evidence_json_string", "[]"),
                                ),
                            )
                    if report:
                        cur.execute(
                            """
                            insert into daily_reports (
                              report_date, report_json_path, report_md_path, total_papers_scanned,
                              total_repos_scanned, total_topics_tracked, max_magnitude, status, run_id
                            )
                            values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            on conflict (report_date) do nothing
                            """,
                            (
                                report.get("report_date"),
                                f"data/reports/{report.get('report_date')}.json",
                                f"data/reports/{report.get('report_date')}.md",
                                report.get("total_papers_scanned", 0),
                                report.get("total_repos_scanned", 0),
                                report.get("total_topics_tracked", 0),
                                report.get("max_magnitude", 0),
                                report.get("status", "generated"),
                                report.get("run_id"),
                            ),
                        )
                conn.commit()
            return NeonWriteResult(True, True, "Neon sync completed")
        except Exception as exc:  # noqa: BLE001 - fallback must preserve local output
            return NeonWriteResult(True, False, f"Neon sync failed; file fallback kept output: {exc}")
