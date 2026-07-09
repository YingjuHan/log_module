#!/usr/bin/env python3
"""Human-friendly CLI viewer for CAE JSONL logs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from tools.pipeline.cae_event_view import filter_events, load_validated_events, validate_and_enrich_item


LEVEL_COLORS = {
    "TRACE": "\033[37m",
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARN": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[35m",
}
RESET = "\033[0m"


def supports_color() -> bool:
    """Return whether the current stdout should receive ANSI colors."""
    return sys.stdout.isatty() and os.environ.get("TERM") != "dumb"


def format_event(event: dict[str, object], color_enabled: bool) -> str:
    """Format one enriched CAE event for terminal output."""
    level = str(event["level"])
    prefix = LEVEL_COLORS.get(level, "") if color_enabled else ""
    suffix = RESET if color_enabled and prefix else ""
    stage = event.get("stage") or event["component"]
    location = f"{event['component']}/{stage}"
    duration = ""
    if event["event_kind"] == "span":
        duration = f" {event['duration_us']}us"
    return (
        f"{event['date']} {event['time']} "
        f"{prefix}{level:<8}{suffix} "
        f"{location:<32} "
        f"{event['event_kind']:<5}"
        f"{duration:<10} "
        f"{event['session']:<12} "
        f"{event.get('action', 'message'):<16} "
        f"{event['message']}"
    )


def load_and_filter(args: argparse.Namespace) -> list[dict[str, object]]:
    """Load validated events and apply all CLI filters."""
    events = load_validated_events(args.input)
    return filter_events(
        events,
        module=args.module,
        stage=args.stage,
        action=args.action,
        level=args.level,
        event_kind=args.event_kind,
        session=args.session,
        min_duration_us=args.min_duration_us,
        contains=args.contains,
        trace_id=args.trace_id,
        event_id=args.event_id,
        parent_event_id=args.parent_event_id,
        job_id=args.job_id,
        node_id=args.node_id,
        mpi_rank=args.mpi_rank,
    )


def emit_events(events: list[dict[str, object]], args: argparse.Namespace) -> None:
    """Emit filtered events as text or JSON."""
    output = events[-args.lines:] if args.lines else events
    color_enabled = supports_color()
    for event in output:
        if args.json:
            print(json.dumps(event, ensure_ascii=False))
        else:
            print(format_event(event, color_enabled))


def follow_file(args: argparse.Namespace) -> None:
    """Follow appended JSONL lines and emit matching events."""
    path = args.input
    color_enabled = supports_color()
    with open(path, encoding="utf-8") as fh:
        start = max(os.path.getsize(path), 0)
        fh.seek(start, os.SEEK_SET)
        while True:
            position = fh.tell()
            line = fh.readline()
            if not line:
                time.sleep(0.5)
                fh.seek(position)
                continue
            try:
                item = json.loads(line)
                event = validate_and_enrich_item(item)
            except json.JSONDecodeError as exc:
                print(f"warning: invalid JSON while following {path}: {exc}", file=sys.stderr)
                continue
            except ValueError as exc:
                print(f"warning: invalid event while following {path}: {exc}", file=sys.stderr)
                continue

            filtered = filter_events(
                [event],
                module=args.module,
                stage=args.stage,
                action=args.action,
                level=args.level,
                event_kind=args.event_kind,
                session=args.session,
                min_duration_us=args.min_duration_us,
                contains=args.contains,
                trace_id=args.trace_id,
                event_id=args.event_id,
                parent_event_id=args.parent_event_id,
                job_id=args.job_id,
                node_id=args.node_id,
                mpi_rank=args.mpi_rank,
            )
            emit_events(filtered, args)


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    parser = argparse.ArgumentParser(description="Tail CAE JSONL logs")
    parser.add_argument("--input", default=os.path.join(project_root, "logs", "cae_events.jsonl"))
    parser.add_argument("--follow", action="store_true", help="Follow appended log lines")
    parser.add_argument("--lines", type=int, default=20, help="Number of matching lines to print")
    parser.add_argument("--module", help="Exact component filter")
    parser.add_argument("--stage", help="Structured stage filter")
    parser.add_argument("--action", help="Structured action filter")
    parser.add_argument("--level", help="Exact level filter")
    parser.add_argument("--event-kind", help="point or span filter")
    parser.add_argument("--session", help="Exact session filter")
    parser.add_argument("--min-duration-us", type=int, help="Minimum duration filter")
    parser.add_argument("--contains", help="Substring filter on event message")
    parser.add_argument("--trace-id", help="Native trace_id filter")
    parser.add_argument("--event-id", help="Schema v1 event_id filter")
    parser.add_argument("--parent-event-id", help="Schema v1 parent_event_id filter")
    parser.add_argument("--job-id", help="Schema v1 job_id filter")
    parser.add_argument("--node-id", help="Schema v1 node_id filter")
    parser.add_argument("--mpi-rank", type=int, help="Schema v1 MPI rank filter")
    parser.add_argument("--json", action="store_true", help="Emit enriched JSON lines")
    return parser


def main() -> None:
    """CLI entry point."""
    args = build_parser().parse_args()
    if not os.path.isfile(args.input):
        raise SystemExit(f"Input log not found: {args.input}")

    if args.follow:
        follow_file(args)
        return

    emit_events(load_and_filter(args), args)


if __name__ == "__main__":
    main()
