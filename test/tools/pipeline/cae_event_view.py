#!/usr/bin/env python3
"""Shared CAE event view helpers for CAE tooling."""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from typing import Any

from tools.pipeline.validate_cae_events import (
    is_legacy_item,
    is_structured_item,
    iter_jsonl_targets,
    validate_jsonl_item,
)


ACTION_PATTERNS = (
    ("started", re.compile(r"\b(started?|begin)\b", re.IGNORECASE)),
    ("completed", re.compile(r"\b(completed?|finished?|ended?)\b", re.IGNORECASE)),
    ("duration", re.compile(r"\bduration\b", re.IGNORECASE)),
    ("created", re.compile(r"\bcreated?\b", re.IGNORECASE)),
    ("applied", re.compile(r"\bappl(?:ied|y)\b", re.IGNORECASE)),
    ("removed", re.compile(r"\bremoved?\b", re.IGNORECASE)),
    ("skipped", re.compile(r"\bskipped?\b", re.IGNORECASE)),
    ("failed", re.compile(r"\bfailed?\b", re.IGNORECASE)),
    ("generated", re.compile(r"\bgenerated?\b", re.IGNORECASE)),
    ("exported", re.compile(r"\bexported?\b", re.IGNORECASE)),
    ("imported", re.compile(r"\bimported?\b", re.IGNORECASE)),
    ("loaded", re.compile(r"\bloaded?\b", re.IGNORECASE)),
    ("computed", re.compile(r"\bcomputed?\b", re.IGNORECASE)),
    ("detected", re.compile(r"\bdetected?\b", re.IGNORECASE)),
    ("extracted", re.compile(r"\bextracted?\b", re.IGNORECASE)),
    ("written", re.compile(r"\bwritten|wrote|write\b", re.IGNORECASE)),
    ("summary", re.compile(r"\bsummary\b", re.IGNORECASE)),
)
KEY_VALUE_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9_]*)="
    r"([+-]?(?:\d+(?:\.\d+)?(?:e[+-]?\d+)?|true|false|[A-Za-z0-9_.-]+))",
    re.IGNORECASE,
)
REASON_RE = re.compile(r"\breason=([A-Za-z0-9_.-]+)", re.IGNORECASE)
ERROR_RE = re.compile(r"\berror=([A-Za-z0-9_.-]+)", re.IGNORECASE)
KNOWN_METRIC_KEYS = {
    "residual",
    "courant",
    "nodes",
    "cells",
    "blocks",
    "fields",
    "timesteps",
    "elements",
    "partitions",
    "matches",
    "max_stress",
    "safety_factor",
    "iteration",
    "watertight_solids",
    "repaired_edges",
    "suppressed_faces",
    "import_seconds",
    "pipeline_seconds",
    "display_seconds",
    "output_seconds",
    "total_seconds",
}


def _coerce_metric_value(raw: str) -> object:
    """Coerce a metric token from a legacy text event."""
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"[+-]?\d+", raw):
        return int(raw)
    try:
        return float(raw)
    except ValueError:
        return raw


def derive_stage(component: str) -> str:
    """Derive a fallback stage name from the component name."""
    if "." in component:
        return component.rsplit(".", 1)[-1]
    return component


def derive_action(message: str) -> str:
    """Derive a stable action label from a legacy message."""
    for name, pattern in ACTION_PATTERNS:
        if pattern.search(message):
            return name
    return "message"


def derive_reason(message: str) -> str | None:
    """Extract a reason/error token from a legacy message."""
    match = REASON_RE.search(message)
    if match:
        return match.group(1)
    match = ERROR_RE.search(message)
    if match:
        return match.group(1)
    return None


def derive_metrics(message: str) -> dict[str, object]:
    """Extract known key=value metric tokens from a legacy message."""
    metrics: dict[str, object] = {}
    for key, value in KEY_VALUE_RE.findall(message):
        if key not in KNOWN_METRIC_KEYS:
            continue
        metrics[key] = _coerce_metric_value(value)
    return metrics


def enrich_event(item: dict[str, Any]) -> dict[str, Any]:
    """Return a structured event view with derived defaults filled in."""
    enriched = dict(item)
    if is_structured_item(item):
        enriched.setdefault("parent_span_id", None)
        enriched.setdefault("object_type", None)
        enriched.setdefault("object_name", None)
        enriched.setdefault("result", None)
        enriched.setdefault("reason", None)
        enriched.setdefault("node_id", None)
        enriched.setdefault("mpi_rank", None)
        enriched.setdefault("schema_version", item.get("schema_version"))
        enriched.setdefault("event_id", item.get("span_id"))
        enriched.setdefault("parent_event_id", item.get("parent_span_id"))
        enriched.setdefault("event_type", "unknown")
        enriched.setdefault("phase", "unknown")
        enriched.setdefault("domain", "unknown")
        enriched.setdefault("entity_type", item.get("object_type") or item.get("component"))
        enriched.setdefault("entity_name", item.get("object_name") or item.get("stage"))
        enriched.setdefault("job_id", item.get("session"))
        enriched.setdefault(
            "global_sequence_id",
            (
                f"{item.get('session', 'unknown')}:{item.get('node_id', 'unknown')}:"
                f"{item.get('mpi_rank')}:{item.get('sequence')}"
            ),
        )
        enriched.setdefault("logical_time", item.get("sequence", 0))
        enriched.setdefault("timestamp_epoch_us", 0)
        enriched.setdefault("monotonic_us", 0)
        enriched.setdefault("metrics", {})
        enriched["derived_from_text"] = False
        return enriched

    if not is_legacy_item(item):
        raise ValueError("unsupported CAE event schema")

    stage = item.get("stage")
    action = item.get("action")
    reason = item.get("reason")
    metrics = item.get("metrics")
    derived_fields_used = False
    if not isinstance(stage, str) or not stage:
        enriched["stage"] = derive_stage(str(item["component"]))
        derived_fields_used = True
    if not isinstance(action, str) or not action:
        enriched["action"] = derive_action(str(item["event"]))
        derived_fields_used = True
    if reason is None:
        enriched["reason"] = derive_reason(str(item["event"]))
        derived_fields_used = True
    if not isinstance(metrics, dict):
        enriched["metrics"] = derive_metrics(str(item["event"]))
        derived_fields_used = True

    enriched["message"] = item["event"]
    enriched.setdefault("trace_id", None)
    enriched.setdefault("span_id", None)
    enriched.setdefault("parent_span_id", None)
    enriched.setdefault("object_type", None)
    enriched.setdefault("object_name", None)
    enriched.setdefault("result", None)
    enriched.setdefault("node_id", None)
    enriched.setdefault("mpi_rank", None)
    enriched.setdefault("schema_version", None)
    enriched.setdefault("event_id", enriched.get("span_id"))
    enriched.setdefault("parent_event_id", enriched.get("parent_span_id"))
    enriched.setdefault("event_type", "unknown")
    enriched.setdefault("phase", "unknown")
    enriched.setdefault("domain", "unknown")
    enriched.setdefault("entity_type", enriched.get("object_type") or enriched.get("component"))
    enriched.setdefault("entity_name", enriched.get("object_name") or enriched.get("stage"))
    enriched.setdefault("job_id", enriched.get("session"))
    enriched.setdefault(
        "global_sequence_id",
        (
            f"{enriched.get('session', 'unknown')}:{enriched.get('node_id', 'unknown')}:"
            f"{enriched.get('mpi_rank')}:{enriched.get('sequence')}"
        ),
    )
    enriched.setdefault("logical_time", enriched.get("sequence", 0))
    enriched.setdefault("timestamp_epoch_us", 0)
    enriched.setdefault("monotonic_us", 0)
    enriched["derived_from_text"] = derived_fields_used
    return enriched


def validate_and_enrich_item(item: Any) -> dict[str, Any]:
    """Validate one parsed row and return its enriched event view."""
    errors = validate_jsonl_item(item, allow_legacy=True)
    if errors:
        raise ValueError("; ".join(errors))
    if not isinstance(item, dict):
        raise ValueError("row is not a JSON object")
    return enrich_event(item)


def load_validated_events(
    path: str | os.PathLike[str],
    invalid_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    """Load, validate, and enrich all events from a JSONL file or directory."""
    events: list[dict[str, Any]] = []
    invalid_rows: list[tuple[str, int, str, str]] = []
    targets = list(iter_jsonl_targets(str(path)))
    if not targets:
        raise SystemExit(f"No JSONL files found in {path}")

    for target in targets:
        if not os.path.isfile(target):
            raise SystemExit(f"Path is not a file: {target}")
        with open(target, encoding="utf-8") as fh:
            for line_no, raw in enumerate(fh, 1):
                if not raw.strip():
                    invalid_rows.append((target, line_no, "blank line", raw))
                    continue
                try:
                    item = json.loads(raw)
                except json.JSONDecodeError as exc:
                    invalid_rows.append((target, line_no, f"invalid JSON: {exc}", raw))
                    continue
                errors = validate_jsonl_item(item, allow_legacy=True)
                if errors:
                    invalid_rows.append((target, line_no, "; ".join(errors), raw))
                    continue
                assert isinstance(item, dict)
                events.append(enrich_event(item))

    if invalid_path:
        with open(invalid_path, "w", encoding="utf-8") as out:
            for target, line_no, reason, raw in invalid_rows:
                out.write(f"{target}:{line_no}: {reason}: {raw}")
                if not raw.endswith("\n"):
                    out.write("\n")

    if invalid_rows:
        target, line_no, reason, _ = invalid_rows[0]
        raise SystemExit(f"Invalid JSONL row in {target}:{line_no}: {reason}")
    return events


def has_future_field_values(events: list[dict[str, Any]], field_name: str) -> bool:
    """Return whether a field has at least one non-empty value."""
    return any(event.get(field_name) not in (None, "") for event in events)


def compute_percentile(values: list[int], percentile: int) -> int:
    """Compute a percentile with the existing ceiling-rank convention."""
    if not values:
        return 0
    ordered = sorted(values)
    rank = int(math.ceil((percentile / 100.0) * len(ordered))) - 1
    rank = min(max(rank, 0), len(ordered) - 1)
    return ordered[rank]


def summarize_metric_series(events: list[dict[str, Any]], metric_name: str) -> dict[str, Any] | None:
    """Summarize numeric samples for a metric key."""
    samples = [
        event["metrics"][metric_name]
        for event in events
        if isinstance(event.get("metrics"), dict)
        and metric_name in event["metrics"]
        and isinstance(event["metrics"][metric_name], (int, float))
    ]
    if not samples:
        return None
    return {
        "sample_count": len(samples),
        "min": min(samples),
        "max": max(samples),
        "first": samples[0],
        "last": samples[-1],
    }


def top_counter_items(counter: Counter, limit: int = 10) -> list[dict[str, object]]:
    """Return the most common counter items in JSON-friendly form."""
    return [{"value": key, "count": count} for key, count in counter.most_common(limit)]


def filter_events(
    events: list[dict[str, Any]],
    *,
    module: str | None = None,
    stage: str | None = None,
    action: str | None = None,
    level: str | None = None,
    event_kind: str | None = None,
    session: str | None = None,
    min_duration_us: int | None = None,
    contains: str | None = None,
    trace_id: str | None = None,
    event_id: str | None = None,
    parent_event_id: str | None = None,
    job_id: str | None = None,
    node_id: str | None = None,
    mpi_rank: int | None = None,
) -> list[dict[str, Any]]:
    """Filter enriched events by CLI-facing fields."""
    selected: list[dict[str, Any]] = []
    contains_folded = contains.casefold() if contains else None
    for event in events:
        if module and event["component"] != module:
            continue
        if stage and event.get("stage") != stage:
            continue
        if action and event.get("action") != action:
            continue
        if level and event["level"] != level:
            continue
        if event_kind and event["event_kind"] != event_kind:
            continue
        if session and event["session"] != session:
            continue
        if min_duration_us is not None and event["duration_us"] < min_duration_us:
            continue
        if trace_id and event.get("trace_id") != trace_id:
            continue
        if event_id and event.get("event_id") != event_id:
            continue
        if parent_event_id and event.get("parent_event_id") != parent_event_id:
            continue
        if job_id and event.get("job_id") != job_id:
            continue
        if node_id and event.get("node_id") != node_id:
            continue
        if mpi_rank is not None and event.get("mpi_rank") != mpi_rank:
            continue
        if contains_folded and contains_folded not in str(event["message"]).casefold():
            continue
        selected.append(event)
    return selected


def count_levels(events: list[dict[str, Any]]) -> Counter:
    """Count events by severity level."""
    return Counter(event["level"] for event in events)
