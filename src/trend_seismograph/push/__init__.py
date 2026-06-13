from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from trend_seismograph.push.email import push_email
from trend_seismograph.push.rss import write_rss
from trend_seismograph.push.telegram import push_telegram
from trend_seismograph.push.webhook import push_webhook
from trend_seismograph.storage.file_store import FileStore


def push_hotspots(store: FileStore, *, force: bool = False, site_url: str = "http://localhost:4321") -> dict[str, Any]:
    snapshot = store.load_hourly_latest()
    if not snapshot:
        return {"ok": False, "error": "data/hotspots/latest.json not found"}
    hotspots = [hotspot for hotspot in snapshot.get("top_hotspots", []) if hotspot.get("push_recommended")]
    index = store.load_push_index()
    now = datetime.now(UTC)
    sent = []
    skipped = []
    for hotspot in hotspots:
        dedupe_key = hotspot.get("dedupe_key")
        if not force and was_pushed(index, dedupe_key, now):
            skipped.append({"dedupe_key": dedupe_key, "reason": "deduped within 24h"})
            continue
        text = render_push_text(hotspot)
        payload = {"hotspot": hotspot, "snapshot_hour": snapshot.get("snapshot_hour")}
        results = [
            push_telegram(text),
            push_email(f"AI 趋势地震仪：{hotspot.get('topic')} 出现异常波动", text),
            push_webhook(payload),
        ]
        event = {
            "event_type": "hotspot",
            "topic": hotspot.get("topic"),
            "magnitude": hotspot.get("magnitude"),
            "severity_label": hotspot.get("severity_label"),
            "payload_json": payload,
            "pushed_channels": [row["channel"] for row in results if not row.get("skipped")],
            "pushed_at": now.isoformat(),
            "dedupe_key": dedupe_key,
            "results": results,
        }
        index.setdefault("events", []).append(event)
        sent.append(event)
    write_rss(store.data_dir / "rss.xml", snapshot.get("top_hotspots", []), site_url=site_url)
    store.save_push_index(index)
    return {"ok": True, "sent": sent, "skipped": skipped, "rss_path": str(store.data_dir / "rss.xml")}


def was_pushed(index: dict[str, Any], dedupe_key: str, now: datetime) -> bool:
    cutoff = now - timedelta(hours=24)
    for event in index.get("events", []):
        if event.get("dedupe_key") != dedupe_key:
            continue
        try:
            pushed_at = datetime.fromisoformat(event.get("pushed_at", "").replace("Z", "+00:00")).astimezone(UTC)
        except Exception:  # noqa: BLE001
            continue
        if pushed_at >= cutoff:
            return True
    return False


def render_push_text(hotspot: dict[str, Any]) -> str:
    drivers = "；".join(hotspot.get("key_drivers", [])[:4]) or "证据有限"
    urls = "\n".join(hotspot.get("source_urls", [])[:3])
    return (
        f"AI 趋势地震仪\n"
        f"M{hotspot.get('magnitude')} {hotspot.get('topic')}：{hotspot.get('severity_label')}\n"
        f"{hotspot.get('summary')}\n"
        f"关键驱动：{drivers}\n"
        f"建议观察后续 3-7 天。\n"
        f"{urls}"
    ).strip()
