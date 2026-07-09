#!/usr/bin/env python3
"""Summarize call-chain capture cost signals from CAE JSONL logs."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from tools.pipeline.cae_event_view import load_validated_events


def percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[index]


def build_callchain_overhead_report(events: list[dict[str, object]]) -> dict[str, object]:
    status_counts: Counter[str] = Counter()
    level_counts: dict[str, Counter[str]] = defaultdict(Counter)
    span_durations_by_status: dict[str, list[int]] = defaultdict(list)

    for event in events:
        status = str(event.get("call_chain_status") or "missing")
        level = str(event.get("level") or "UNKNOWN")
        status_counts[status] += 1
        level_counts[level][status] += 1
        if event.get("event_kind") == "span" and isinstance(event.get("duration_us"), int):
            span_durations_by_status[status].append(int(event["duration_us"]))

    duration_summary = {
        status: {
            "span_count": len(values),
            "p50_duration_us": percentile(values, 50),
            "p95_duration_us": percentile(values, 95),
            "max_duration_us": max(values) if values else 0,
        }
        for status, values in sorted(span_durations_by_status.items())
    }
    total = sum(status_counts.values())
    captured = status_counts.get("captured", 0)
    return {
        "event_count": total,
        "call_chain_status_counts": dict(sorted(status_counts.items())),
        "capture_rate": (captured / total) if total else 0.0,
        "level_status_counts": {
            level: dict(sorted(counts.items()))
            for level, counts in sorted(level_counts.items())
        },
        "span_duration_by_call_chain_status": duration_summary,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize call-chain capture overhead signals")
    parser.add_argument("--input", default=str(Path("logs") / "cae_events.jsonl"))
    parser.add_argument("--output", default=None, help="Optional JSON report path")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        events = load_validated_events(args.input)
        report = build_callchain_overhead_report(events)
    except (FileNotFoundError, SystemExit, ValueError) as exc:
        sys.exit(str(exc))

    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
