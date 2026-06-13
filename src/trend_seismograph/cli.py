from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from trend_seismograph.config import ensure_data_dirs, load_config
from trend_seismograph.push import push_hotspots
from trend_seismograph.qa import qa_daily, qa_hourly
from trend_seismograph.reports.generator import run_daily
from trend_seismograph.reports.hourly import fetch_sources, parse_hour, run_hourly
from trend_seismograph.storage.file_store import FileStore
from trend_seismograph.storage.neon_store import NeonStore


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()
    ensure_data_dirs(config.data_dir)
    source_filter = set(args.source.split(",")) if getattr(args, "source", None) else None
    dry_run = parse_bool(getattr(args, "dry_run", False))
    force = parse_bool(getattr(args, "force", False))
    no_push = parse_bool(getattr(args, "no_push", False))
    storage = getattr(args, "storage", "file")
    try:
        if args.command == "fetch":
            result = cmd_fetch(config, args.date, source_filter=source_filter)
        elif args.command == "fetch-hourly":
            hour_dt = parse_hour(args.hour)
            result = cmd_fetch(config, args.hour[:10], hour=hour_dt, source_filter=source_filter)
        elif args.command == "analyze":
            result = run_daily(
                config=config,
                date=args.date,
                lookback_hours=args.lookback_hours,
                storage="file",
                source_filter=source_filter,
                force=force,
                no_push=True,
                dry_run=True,
            )
        elif args.command == "analyze-hourly":
            result = run_hourly(
                config=config,
                hour=args.hour,
                storage="file",
                source_filter=source_filter,
                force=force,
                no_push=True,
                dry_run=True,
            )
        elif args.command in {"report", "run-daily"}:
            result = run_daily(
                config=config,
                date=args.date,
                lookback_hours=getattr(args, "lookback_hours", 72),
                storage=storage,
                source_filter=source_filter,
                force=force,
                force_report=parse_bool(getattr(args, "force_report", False)),
                no_push=no_push,
                dry_run=dry_run,
            )
        elif args.command == "run-hourly":
            result = run_hourly(
                config=config,
                hour=args.hour,
                storage=storage,
                source_filter=source_filter,
                force=force,
                no_push=no_push,
                dry_run=dry_run,
            )
        elif args.command == "sync-neon":
            report = FileStore(config.data_dir).load_report(args.date)
            result = NeonStore().sync([], report=report or {})
        elif args.command == "push-hotspots":
            result = push_hotspots(FileStore(config.data_dir), force=force)
        elif args.command == "qa":
            result = qa_daily(config.data_dir, args.date).as_dict()
        elif args.command == "qa-hourly":
            result = qa_hourly(config.data_dir, args.hour).as_dict()
        elif args.command == "backfill":
            result = cmd_backfill(config, args.start_date, args.end_date, storage=storage, force=force, no_push=True, dry_run=dry_run)
        else:
            parser.error(f"unknown command {args.command}")
            return 2
        print_json(result)
        if isinstance(result, dict) and result.get("ok") is False:
            return 1
        if hasattr(result, "ok") and not result.ok:
            return 1
        if isinstance(result, dict) and result.get("errors"):
            return 1
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        print_json({"ok": False, "error": str(exc)})
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m trend_seismograph")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--dry-run", default=False)
        p.add_argument("--force", default=False)
        p.add_argument("--no-push", default=False)
        p.add_argument("--storage", choices=["file", "neon", "both"], default="file")
        p.add_argument("--source", default=None, help="Comma-separated source names, e.g. arxiv,github,openalex")

    p = sub.add_parser("fetch")
    p.add_argument("--date", required=True)
    add_common(p)
    p = sub.add_parser("fetch-hourly")
    p.add_argument("--hour", required=True)
    add_common(p)
    p = sub.add_parser("analyze")
    p.add_argument("--date", required=True)
    p.add_argument("--lookback-hours", type=int, default=72)
    add_common(p)
    p = sub.add_parser("analyze-hourly")
    p.add_argument("--hour", required=True)
    add_common(p)
    p = sub.add_parser("report")
    p.add_argument("--date", required=True)
    p.add_argument("--lookback-hours", type=int, default=72)
    p.add_argument("--force-report", default=False)
    add_common(p)
    p = sub.add_parser("run-hourly")
    p.add_argument("--hour", required=True)
    add_common(p)
    p = sub.add_parser("run-daily")
    p.add_argument("--date", required=True)
    p.add_argument("--lookback-hours", type=int, default=72)
    p.add_argument("--force-report", default=False)
    add_common(p)
    p = sub.add_parser("sync-neon")
    p.add_argument("--date", required=True)
    add_common(p)
    p = sub.add_parser("push-hotspots")
    p.add_argument("--hour", default=None)
    add_common(p)
    p = sub.add_parser("qa")
    p.add_argument("--date", required=True)
    p = sub.add_parser("qa-hourly")
    p.add_argument("--hour", required=True)
    p = sub.add_parser("backfill")
    p.add_argument("--from", dest="start_date", required=True)
    p.add_argument("--to", dest="end_date", required=True)
    add_common(p)
    return parser


def cmd_fetch(config, date: str, *, hour: datetime | None = None, source_filter: set[str] | None = None) -> dict[str, Any]:
    end = hour + timedelta(hours=1) if hour else datetime.fromisoformat(date).replace(tzinfo=UTC) + timedelta(days=1)
    start = hour if hour else end - timedelta(days=1)
    fetched = fetch_sources(config=config, start=start, end=end, source_filter=source_filter)
    store = FileStore(config.data_dir)
    run_id = f"fetch-{date}-{datetime.now(UTC).strftime('%H%M%S')}"
    for result in fetched:
        store.save_raw_items(run_id, result.source_name, result.items)
    return {
        "run_id": run_id,
        "date": date,
        "source_status": [result.status() for result in fetched],
        "total_items": sum(len(result.items) for result in fetched),
    }


def cmd_backfill(config, start_date: str, end_date: str, *, storage: str, force: bool, no_push: bool, dry_run: bool) -> dict[str, Any]:
    start = datetime.fromisoformat(start_date).date()
    end = datetime.fromisoformat(end_date).date()
    rows = []
    current = start
    while current <= end:
        rows.append(
            run_daily(
                config=config,
                date=current.isoformat(),
                storage=storage,
                force=force,
                force_report=False,
                no_push=no_push,
                dry_run=dry_run,
            )
        )
        current += timedelta(days=1)
    return {"ok": True, "reports": rows}


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "y"}


def print_json(value: Any) -> None:
    if hasattr(value, "__dict__"):
        value = value.__dict__
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    sys.exit(main())
