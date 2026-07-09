#!/usr/bin/env python3
"""Summarize CAE JSONL logs into JSON/CSV alert artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.pipeline.cae_event_graph import build_observability_artifacts
from tools.pipeline.cae_event_view import (
    compute_percentile,
    load_validated_events,
    summarize_metric_series,
    top_counter_items,
)


SCHEMA_VERSION = "patch3-summary-v1"


def utc_now_iso() -> str:
    """Return the current UTC time in stable ISO-8601 form."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def compute_span_stats(events: list[dict[str, Any]]) -> dict[str, int]:
    """Compute aggregate duration statistics for span events."""
    durations = [event["duration_us"] for event in events if event["event_kind"] == "span"]
    if not durations:
        return {"count": 0, "avg_us": 0, "p90_us": 0, "p95_us": 0, "p99_us": 0, "max_us": 0}
    return {
        "count": len(durations),
        "avg_us": sum(durations) // len(durations),
        "p90_us": compute_percentile(durations, 90),
        "p95_us": compute_percentile(durations, 95),
        "p99_us": compute_percentile(durations, 99),
        "max_us": max(durations),
    }


def ratio(numerator: float, denominator: float) -> float:
    """Return a safe ratio with zero protection."""
    if not denominator:
        return 0.0
    return numerator / denominator


def build_logger_health_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize the latest logger health snapshot event."""
    health_events = [
        event
        for event in events
        if event.get("component") == "Logger" and event.get("action") == "health_snapshot"
    ]
    if not health_events:
        return {
            "health_event_count": 0,
            "latest_sequence": None,
            "latest_timestamp_epoch_us": None,
            "latest_metrics": {},
            "segments_created": 0,
        }

    latest = max(
        health_events,
        key=lambda event: (
            event.get("timestamp_epoch_us") or 0,
            event.get("logical_time") or 0,
            event.get("sequence") or 0,
        ),
    )
    metrics = latest.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    segments_created = metrics.get("analysis_segments_created", 0)
    if not isinstance(segments_created, (int, float)):
        segments_created = 0

    return {
        "health_event_count": len(health_events),
        "latest_sequence": latest.get("sequence"),
        "latest_timestamp_epoch_us": latest.get("timestamp_epoch_us"),
        "latest_metrics": dict(metrics),
        "segments_created": segments_created,
    }


def load_alert_config(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load alert thresholds from a JSON object."""
    with open(path, encoding="utf-8") as fh:
        config = json.load(fh)
    if not isinstance(config, dict):
        raise SystemExit(f"Alert config must be a JSON object: {path}")
    return config


def build_summary(
    events: list[dict[str, Any]],
    source_file: str | os.PathLike[str],
    alert_config_path: str | os.PathLike[str],
) -> dict[str, Any]:
    """Build a complete CAE event summary payload."""
    components = Counter(event["component"] for event in events)
    stages = Counter(event["stage"] for event in events)
    levels = Counter(event["level"] for event in events)
    event_kinds = Counter(event["event_kind"] for event in events)
    actions = Counter(event["action"] for event in events)
    reasons = Counter(event["reason"] for event in events if event.get("reason"))
    sessions = {event["session"] for event in events}
    traces = Counter(event["trace_id"] for event in events if event.get("trace_id"))
    nodes = Counter(event["node_id"] for event in events if event.get("node_id"))
    mpi_ranks = Counter(str(event["mpi_rank"]) for event in events if event.get("mpi_rank") is not None)
    modules = set(components)
    derived_fields_used = any(event.get("derived_from_text") for event in events)

    by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_module[event["component"]].append(event)

    metric_summary = {}
    for metric_name in ("residual", "nodes", "cells", "courant", "max_stress", "safety_factor"):
        metric_stats = summarize_metric_series(events, metric_name)
        if metric_stats:
            metric_summary[metric_name] = metric_stats

    observability = build_observability_artifacts(events)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_file": os.path.abspath(source_file),
        "generated_at": utc_now_iso(),
        "derived_fields_used": derived_fields_used,
        "alert_config_file": os.path.abspath(alert_config_path),
        "total_events": len(events),
        "point_events": event_kinds.get("point", 0),
        "span_events": event_kinds.get("span", 0),
        "module_count": len(modules),
        "session_count": len(sessions),
        "trace_count": len(traces),
        "node_count": len(nodes),
        "mpi_rank_count": len(mpi_ranks),
        "distributions": {
            "component": dict(sorted(components.items())),
            "stage": dict(sorted(stages.items())),
            "level": dict(sorted(levels.items())),
            "event_kind": dict(sorted(event_kinds.items())),
            "node_id": dict(sorted(nodes.items())),
            "mpi_rank": dict(sorted(mpi_ranks.items(), key=lambda item: item[0])),
        },
        "span_stats": {
            "global": compute_span_stats(events),
            "by_component": {
                component: compute_span_stats(component_events)
                for component, component_events in sorted(by_module.items())
            },
        },
        "top_actions": top_counter_items(actions),
        "top_reasons": top_counter_items(reasons),
        "top_traces": top_counter_items(traces),
        "top_nodes": top_counter_items(nodes),
        "metric_summary": metric_summary,
        "residual_summary": summarize_metric_series(events, "residual"),
        "dag_stats": observability["stats"],
        "logger_health": build_logger_health_summary(events),
        "alerts_summary": {"skipped_metrics": []},
    }


def build_module_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build per-component summary rows for CSV output."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[event["component"]].append(event)

    rows: list[dict[str, Any]] = []
    for component, component_events in sorted(grouped.items()):
        span_stats = compute_span_stats(component_events)
        levels = Counter(event["level"] for event in component_events)
        rows.append({
            "component": component,
            "total_events": len(component_events),
            "point_events": sum(1 for event in component_events if event["event_kind"] == "point"),
            "span_events": span_stats["count"],
            "error_events": levels.get("ERROR", 0) + levels.get("CRITICAL", 0),
            "warn_events": levels.get("WARN", 0),
            "avg_span_us": span_stats["avg_us"],
            "p95_span_us": span_stats["p95_us"],
            "max_span_us": span_stats["max_us"],
            "session_count": len({event["session"] for event in component_events}),
        })
    return rows


def append_alert(
    alerts: list[dict[str, Any]],
    rule_id: str,
    severity: str,
    scope: str,
    observed: Any,
    threshold: Any,
    message: str,
) -> None:
    """Append one alert record."""
    alerts.append({
        "rule_id": rule_id,
        "severity": severity,
        "scope": scope,
        "observed": observed,
        "threshold": threshold,
        "message": message,
    })


def evaluate_alerts(
    events: list[dict[str, Any]],
    summary: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Evaluate configured threshold alerts against events and summary data."""
    alerts: list[dict[str, Any]] = []
    skipped: list[str] = []
    total_events = summary["total_events"]
    level_counts = Counter(event["level"] for event in events)
    error_events = level_counts.get("ERROR", 0) + level_counts.get("CRITICAL", 0)
    warn_events = level_counts.get("WARN", 0)
    error_rate = ratio(error_events, total_events)
    residual_summary = summary.get("residual_summary")

    global_rules = config.get("global", {})
    modules_rules = config.get("modules", {})

    global_span_threshold = global_rules.get("span_p95_us")
    if global_span_threshold is not None:
        observed = summary["span_stats"]["global"]["p95_us"]
        if observed > global_span_threshold:
            append_alert(
                alerts,
                "global.span_p95_us",
                "warning",
                "global",
                observed,
                global_span_threshold,
                f"Global span p95_us {observed} exceeded threshold {global_span_threshold}.",
            )

    global_error_rate_threshold = global_rules.get("error_rate")
    if global_error_rate_threshold is not None and error_rate > global_error_rate_threshold:
        append_alert(
            alerts,
            "global.error_rate",
            "warning",
            "global",
            round(error_rate, 6),
            global_error_rate_threshold,
            f"Global error rate {error_rate:.6f} exceeded threshold {global_error_rate_threshold}.",
        )

    global_warn_threshold = global_rules.get("warn_count")
    if global_warn_threshold is not None and warn_events > global_warn_threshold:
        append_alert(
            alerts,
            "global.warn_count",
            "info",
            "global",
            warn_events,
            global_warn_threshold,
            f"Global warn count {warn_events} exceeded threshold {global_warn_threshold}.",
        )

    residual_last_threshold = global_rules.get("residual_last_gt")
    if residual_last_threshold is not None:
        if residual_summary:
            observed = residual_summary["last"]
            if observed > residual_last_threshold:
                append_alert(
                    alerts,
                    "global.residual_last_gt",
                    "warning",
                    "global",
                    observed,
                    residual_last_threshold,
                    f"Final residual {observed} exceeded threshold {residual_last_threshold}.",
                )
        else:
            skipped.append("residual_last_gt")

    residual_drop_threshold = global_rules.get("residual_drop_ratio_lt")
    if residual_drop_threshold is not None:
        if residual_summary:
            first = residual_summary["first"]
            last = residual_summary["last"]
            observed = 0.0 if first == 0 else 1.0 - (last / first)
            if observed < residual_drop_threshold:
                append_alert(
                    alerts,
                    "global.residual_drop_ratio_lt",
                    "warning",
                    "global",
                    round(observed, 6),
                    residual_drop_threshold,
                    f"Residual drop ratio {observed:.6f} stayed below threshold {residual_drop_threshold}.",
                )
        else:
            skipped.append("residual_drop_ratio_lt")

    module_rows = build_module_rows(events)
    module_index = {row["component"]: row for row in module_rows}
    module_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        module_groups[event["component"]].append(event)

    for component, thresholds in modules_rules.items():
        row = module_index.get(component)
        if not row:
            continue
        module_events = module_groups[component]
        module_total = len(module_events)
        module_levels = Counter(event["level"] for event in module_events)
        module_error_rate = ratio(
            module_levels.get("ERROR", 0) + module_levels.get("CRITICAL", 0),
            module_total,
        )
        span_p95_threshold = thresholds.get("span_p95_us")
        if span_p95_threshold is not None and row["p95_span_us"] > span_p95_threshold:
            append_alert(
                alerts,
                "module.span_p95_us",
                "warning",
                component,
                row["p95_span_us"],
                span_p95_threshold,
                f"Module {component} span p95_us {row['p95_span_us']} exceeded threshold {span_p95_threshold}.",
            )
        module_error_rate_threshold = thresholds.get("error_rate")
        if module_error_rate_threshold is not None and module_error_rate > module_error_rate_threshold:
            append_alert(
                alerts,
                "module.error_rate",
                "warning",
                component,
                round(module_error_rate, 6),
                module_error_rate_threshold,
                f"Module {component} error rate {module_error_rate:.6f} exceeded threshold {module_error_rate_threshold}.",
            )

    summary["alerts_summary"]["skipped_metrics"] = skipped
    return alerts


def write_json(path: str | os.PathLike[str], payload: Any) -> None:
    """Write a JSON payload with stable formatting."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def write_csv(path: str | os.PathLike[str], rows: list[dict[str, Any]]) -> None:
    """Write per-component summary rows to CSV."""
    fieldnames = [
        "component",
        "total_events",
        "point_events",
        "span_events",
        "error_events",
        "warn_events",
        "avg_span_us",
        "p95_span_us",
        "max_span_us",
        "session_count",
    ]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def maybe_write_enriched_jsonl(
    path: str | os.PathLike[str] | None,
    events: list[dict[str, Any]],
) -> None:
    """Optionally write enriched JSONL events."""
    if not path:
        return
    with open(path, "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def build_alerts_payload(
    source_file: str | os.PathLike[str],
    alert_config_path: str | os.PathLike[str],
    alerts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the alert artifact payload."""
    return {
        "source_file": os.path.abspath(source_file),
        "generated_at": utc_now_iso(),
        "config_file": os.path.abspath(alert_config_path),
        "alerts": alerts,
    }


def write_summary_artifacts(
    *,
    input_path: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    alert_config_path: str | os.PathLike[str],
    write_enriched_jsonl_path: str | os.PathLike[str] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Path | None]:
    """Write summary JSON, module CSV, alert JSON, and optional enriched JSONL."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if events is None:
        events = load_validated_events(str(input_path))
    if not events:
        raise ValueError(f"No valid events found in {input_path}")

    config = load_alert_config(alert_config_path)
    summary = build_summary(events, input_path, alert_config_path)
    module_rows = build_module_rows(events)
    alerts = evaluate_alerts(events, summary, config)

    summary_path = output_path / "cae_summary.json"
    module_csv_path = output_path / "cae_module_stats.csv"
    alerts_path = output_path / "cae_alerts.json"

    write_json(summary_path, summary)
    write_csv(module_csv_path, module_rows)
    write_json(alerts_path, build_alerts_payload(input_path, alert_config_path, alerts))
    maybe_write_enriched_jsonl(write_enriched_jsonl_path, events)

    return {
        "summary": summary_path,
        "module_csv": module_csv_path,
        "alerts": alerts_path,
        "enriched_jsonl": Path(write_enriched_jsonl_path) if write_enriched_jsonl_path else None,
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    parser = argparse.ArgumentParser(description="Summarize CAE JSONL logs")
    parser.add_argument("--input", default=os.path.join(project_root, "logs", "cae_events.jsonl"))
    parser.add_argument("--output-dir", default=os.path.join(project_root, "reports"))
    parser.add_argument("--alert-config", default=os.path.join(project_root, "config", "cae_alerts.json"))
    parser.add_argument("--write-enriched-jsonl", help="Optional path to write enriched JSONL view")
    return parser


def main() -> None:
    """CLI entry point."""
    args = build_parser().parse_args()
    outputs = write_summary_artifacts(
        input_path=args.input,
        output_dir=args.output_dir,
        alert_config_path=args.alert_config,
        write_enriched_jsonl_path=args.write_enriched_jsonl,
    )

    print(f"Wrote {outputs['summary']}")
    print(f"Wrote {outputs['module_csv']}")
    print(f"Wrote {outputs['alerts']}")
    if args.write_enriched_jsonl:
        print(f"Wrote {os.path.abspath(args.write_enriched_jsonl)}")


if __name__ == "__main__":
    main()
