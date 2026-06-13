from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg
import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    url = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")
    if not url:
        print("DATABASE_URL/NEON_DATABASE_URL is required")
        return 1
    taxonomy = yaml.safe_load((ROOT / "config" / "trend_taxonomy.yml").read_text(encoding="utf-8"))
    institutions = yaml.safe_load((ROOT / "config" / "institutions.yml").read_text(encoding="utf-8"))
    sources = yaml.safe_load((ROOT / "config" / "sources.yml").read_text(encoding="utf-8"))
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            for source in sources.get("sources", []):
                cur.execute(
                    """
                    insert into sources (source_type, source_name, base_url, reliability_weight, enabled, rate_limit_policy)
                    values (%s,%s,%s,%s,%s,%s::jsonb)
                    on conflict (source_name) do update set
                      source_type = excluded.source_type,
                      base_url = excluded.base_url,
                      reliability_weight = excluded.reliability_weight,
                      enabled = excluded.enabled,
                      rate_limit_policy = excluded.rate_limit_policy,
                      updated_at = now()
                    """,
                    (
                        source.get("source_type"),
                        source.get("source_name"),
                        source.get("base_url"),
                        source.get("reliability_weight", 0.75),
                        source.get("enabled", True),
                        json.dumps(source.get("rate_limit_policy", {})),
                    ),
                )
            for topic in taxonomy.get("topics", []):
                cur.execute(
                    """
                    insert into topics (canonical_name, aliases, category, priority_weight, watchlist_level, enabled)
                    values (%s,%s::jsonb,%s,%s,%s,true)
                    on conflict (canonical_name) do update set
                      aliases = excluded.aliases,
                      category = excluded.category,
                      priority_weight = excluded.priority_weight
                    """,
                    (
                        topic["canonical_name"],
                        json.dumps(topic.get("aliases", []), ensure_ascii=False),
                        topic.get("category"),
                        topic.get("priority_weight", 1.0),
                        str(topic.get("watchlist_default_threshold", "")),
                    ),
                )
            for inst in institutions.get("institutions", []):
                cur.execute(
                    """
                    insert into institutions (canonical_name, aliases, country_or_region, institution_type, weight)
                    values (%s,%s::jsonb,%s,%s,%s)
                    on conflict (canonical_name) do update set
                      aliases = excluded.aliases,
                      country_or_region = excluded.country_or_region,
                      institution_type = excluded.institution_type,
                      weight = excluded.weight
                    """,
                    (
                        inst["canonical_name"],
                        json.dumps(inst.get("aliases", []), ensure_ascii=False),
                        inst.get("country_or_region"),
                        inst.get("institution_type"),
                        inst.get("weight", 0.75),
                    ),
                )
        conn.commit()
    print("seed completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
