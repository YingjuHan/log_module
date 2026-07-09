#!/usr/bin/env python3
"""Validate CAE JSONL analysis logs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Any

from tools.pipeline.cae_event_schema import (
    DOMAINS,
    EVENT_PHASES,
    EVENT_TYPES,
    SCHEMA_VERSION,
    V1_NULLABLE_STRING_FIELDS,
    V1_REQUIRED_INTEGER_FIELDS,
    V1_REQUIRED_STRING_FIELDS,
)


VALID_EVENT_KINDS = {"point", "span"}
TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SPAN_ID_RE = re.compile(r"^[0-9a-f]{16}$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}$")

LEGACY_REQUIRED_STRING_FIELDS = (
    "date",
    "time",
    "source",
    "component",
    "level",
    "event",
    "event_kind",
    "session",
    "thread_name",
)
LEGACY_REQUIRED_INTEGER_FIELDS = ("outcome", "duration_us", "size", "sequence")

STRUCTURED_REQUIRED_STRING_FIELDS = (
    "timestamp",
    "date",
    "time",
    "source",
    "component",
    "stage",
    "action",
    "level",
    "message",
    "event_kind",
    "trace_id",
    "span_id",
    "session",
    "thread_name",
)
STRUCTURED_REQUIRED_INTEGER_FIELDS = ("duration_us", "size", "sequence")
STRUCTURED_OPTIONAL_NULLABLE_STRING_FIELDS = (
    "parent_span_id",
    "object_type",
    "object_name",
    "result",
    "reason",
)
STRUCTURED_OPTIONAL_STRING_FIELDS = ("node_id",)
STRUCTURED_HINT_FIELDS = {
    "timestamp",
    "stage",
    "action",
    "message",
    "trace_id",
    "span_id",
    "parent_span_id",
    "object_type",
    "object_name",
    "result",
    "reason",
    "metrics",
    "schema_version",
    "event_id",
    "event_type",
    "phase",
    "domain",
    "timestamp_epoch_us",
}
SCHEMA_V1_MARKER_FIELDS = {
    "schema_version",
    "event_id",
    "parent_event_id",
    "event_type",
    "phase",
    "domain",
    "entity_type",
    "entity_name",
    "job_id",
    "global_sequence_id",
    "logical_time",
    "timestamp_epoch_us",
    "monotonic_us",
}


def is_structured_item(item: Any) -> bool:
    """Return whether a JSON item looks like the structured CAE schema."""
    return isinstance(item, dict) and any(field in item for field in STRUCTURED_HINT_FIELDS)


def is_legacy_item(item: Any) -> bool:
    """Return whether a JSON item looks like the legacy text-derived schema."""
    return isinstance(item, dict) and "event" in item and "message" not in item


def validate_string_fields(item: dict[str, Any], fields: tuple[str, ...], errors: list[str]) -> None:
    """Append validation errors for required non-empty string fields."""
    for field in fields:
        value = item.get(field)
        if not isinstance(value, str) or value == "":
            errors.append(f"{field} must be a non-empty string")


def validate_integer_fields(item: dict[str, Any], fields: tuple[str, ...], errors: list[str]) -> None:
    """Append validation errors for required integer fields."""
    for field in fields:
        value = item.get(field)
        if not isinstance(value, int):
            errors.append(f"{field} must be an integer")


def validate_nullable_string_fields(
    item: dict[str, Any],
    fields: tuple[str, ...],
    errors: list[str],
) -> None:
    """Append validation errors for nullable string fields."""
    for field in fields:
        value = item.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(f"{field} must be null or a string")


def validate_optional_string_fields(
    item: dict[str, Any],
    fields: tuple[str, ...],
    errors: list[str],
) -> None:
    """Append validation errors for optional non-empty string fields."""
    for field in fields:
        value = item.get(field)
        if value is not None and (not isinstance(value, str) or value == ""):
            errors.append(f"{field} must be absent or a non-empty string")


def validate_common_fields(item: dict[str, Any], errors: list[str]) -> None:
    """Validate fields shared by legacy and structured rows."""
    event_kind = item.get("event_kind")
    if isinstance(event_kind, str) and event_kind not in VALID_EVENT_KINDS:
        errors.append("event_kind must be one of: point, span")

    duration = item.get("duration_us")
    if isinstance(duration, int) and duration < 0:
        errors.append("duration_us must be non-negative")
    if isinstance(duration, int) and event_kind == "point" and duration != 0:
        errors.append("point events must have duration_us == 0")
    if isinstance(duration, int) and event_kind == "span" and duration <= 0:
        errors.append("span events must have duration_us > 0")

    size = item.get("size")
    if isinstance(size, int) and size < 0:
        errors.append("size must be non-negative")


def validate_legacy_item(item: dict[str, Any]) -> list[str]:
    """Validate a legacy CAE JSONL row."""
    errors: list[str] = []
    validate_string_fields(item, LEGACY_REQUIRED_STRING_FIELDS, errors)
    validate_integer_fields(item, LEGACY_REQUIRED_INTEGER_FIELDS, errors)
    validate_common_fields(item, errors)
    return errors


def validate_non_negative_integer(item: dict[str, Any], field: str, errors: list[str]) -> None:
    """Append validation errors for a required non-negative integer field."""
    value = item.get(field)
    if not isinstance(value, int):
        errors.append(f"{field} must be an integer")
    elif value < 0:
        errors.append(f"{field} must be non-negative")


def validate_schema_v1_fields(
    item: dict[str, Any],
    errors: list[str],
    *,
    require_schema_version: bool = False,
) -> None:
    """Validate additive schema v1 fields when present or explicitly required."""
    schema_version = item.get("schema_version")
    has_v1_marker = schema_version is not None or any(field in item for field in SCHEMA_V1_MARKER_FIELDS)
    if require_schema_version or has_v1_marker:
        if schema_version != SCHEMA_VERSION:
            errors.append(f"schema_version must be '{SCHEMA_VERSION}'")
        validate_string_fields(item, V1_REQUIRED_STRING_FIELDS[1:], errors)
        validate_nullable_string_fields(item, V1_NULLABLE_STRING_FIELDS, errors)
        for field in V1_REQUIRED_INTEGER_FIELDS:
            validate_non_negative_integer(item, field, errors)

    if not (require_schema_version or has_v1_marker):
        return

    event_type = item.get("event_type")
    phase = item.get("phase")
    domain = item.get("domain")
    event_id = item.get("event_id")
    span_id = item.get("span_id")
    parent_event_id = item.get("parent_event_id")
    parent_span_id = item.get("parent_span_id")

    if isinstance(event_type, str) and event_type not in EVENT_TYPES:
        errors.append(f"event_type must be one of: {', '.join(sorted(EVENT_TYPES))}")
    if isinstance(phase, str) and phase not in EVENT_PHASES:
        errors.append(f"phase must be one of: {', '.join(sorted(EVENT_PHASES))}")
    if isinstance(domain, str) and domain not in DOMAINS:
        errors.append(f"domain must be one of: {', '.join(sorted(DOMAINS))}")
    if isinstance(event_id, str) and isinstance(span_id, str) and event_id != span_id:
        errors.append("event_id must match span_id when both are present")
    if (
        parent_event_id is not None
        and parent_span_id is not None
        and isinstance(parent_event_id, str)
        and isinstance(parent_span_id, str)
        and parent_event_id != parent_span_id
    ):
        errors.append("parent_event_id must match parent_span_id when both are present")


def validate_structured_item(
    item: dict[str, Any],
    *,
    require_schema_version: bool = False,
) -> list[str]:
    """Validate a structured CAE JSONL row."""
    errors: list[str] = []
    validate_string_fields(item, STRUCTURED_REQUIRED_STRING_FIELDS, errors)
    validate_integer_fields(item, STRUCTURED_REQUIRED_INTEGER_FIELDS, errors)
    validate_nullable_string_fields(item, STRUCTURED_OPTIONAL_NULLABLE_STRING_FIELDS, errors)
    validate_optional_string_fields(item, STRUCTURED_OPTIONAL_STRING_FIELDS, errors)
    validate_common_fields(item, errors)

    timestamp = item.get("timestamp")
    trace_id = item.get("trace_id")
    span_id = item.get("span_id")
    parent_span_id = item.get("parent_span_id")
    mpi_rank = item.get("mpi_rank")
    metrics = item.get("metrics")

    if isinstance(timestamp, str) and not TIMESTAMP_RE.fullmatch(timestamp):
        errors.append("timestamp must be ISO local time with millisecond precision")
    if isinstance(trace_id, str) and not TRACE_ID_RE.fullmatch(trace_id):
        errors.append("trace_id must be 32 lowercase hex characters")
    if isinstance(span_id, str) and not SPAN_ID_RE.fullmatch(span_id):
        errors.append("span_id must be 16 lowercase hex characters")
    if parent_span_id is not None and not (
        isinstance(parent_span_id, str) and SPAN_ID_RE.fullmatch(parent_span_id)
    ):
        errors.append("parent_span_id must be null or 16 lowercase hex characters")
    if mpi_rank is not None and not isinstance(mpi_rank, int):
        errors.append("mpi_rank must be null or an integer")
    if not isinstance(metrics, dict):
        errors.append("metrics must be a JSON object")
    elif any(not isinstance(value, (int, float, bool, str)) for value in metrics.values()):
        errors.append("metrics values must be number, bool, or string")

    validate_schema_v1_fields(item, errors, require_schema_version=require_schema_version)
    return errors


def validate_jsonl_item(
    item: Any,
    *,
    allow_legacy: bool = False,
    require_schema_version: str | None = None,
) -> list[str]:
    """Validate one parsed JSONL item and return a list of errors."""
    if not isinstance(item, dict):
        return ["row is not a JSON object"]
    require_v1 = require_schema_version == SCHEMA_VERSION
    if require_schema_version not in (None, SCHEMA_VERSION):
        return [f"unsupported required schema_version: {require_schema_version}"]
    if is_structured_item(item) or not is_legacy_item(item):
        return validate_structured_item(item, require_schema_version=require_v1)
    if allow_legacy:
        return validate_legacy_item(item)
    return ["legacy schema is not accepted by the Patch 3 validator"]


def collect_jsonl_stats(
    path: str,
    invalid_path: str | None = None,
    *,
    allow_legacy: bool = False,
    require_schema_version: str | None = None,
) -> tuple[dict[str, Any], list[tuple[int, str, str]]]:
    """Collect high-level stats and invalid rows from one JSONL file."""
    stats: dict[str, Any] = {
        "line_count": 0,
        "modules": set(),
        "sessions": set(),
        "traces": set(),
        "event_kind_counts": Counter(),
        "durations_by_module": defaultdict(lambda: {"count": 0, "sum": 0, "max": 0}),
    }
    invalid_rows: list[tuple[int, str, str]] = []

    with open(path, encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            if not raw.strip():
                invalid_rows.append((line_no, "blank line", raw))
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError as exc:
                invalid_rows.append((line_no, f"invalid JSON: {exc}", raw))
                continue

            errors = validate_jsonl_item(
                item,
                allow_legacy=allow_legacy,
                require_schema_version=require_schema_version,
            )
            if errors:
                invalid_rows.append((line_no, "; ".join(errors), raw))
                continue

            stats["line_count"] += 1
            stats["modules"].add(item["component"])
            stats["sessions"].add(item["session"])
            if isinstance(item.get("trace_id"), str):
                stats["traces"].add(item["trace_id"])
            stats["event_kind_counts"][item["event_kind"]] += 1

            if item["event_kind"] == "span":
                duration = item["duration_us"]
                duration_stats = stats["durations_by_module"][item["component"]]
                duration_stats["count"] += 1
                duration_stats["sum"] += duration
                duration_stats["max"] = max(duration_stats["max"], duration)

    if invalid_path:
        with open(invalid_path, "w", encoding="utf-8") as out:
            for line_no, reason, raw in invalid_rows:
                out.write(f"{path}:{line_no}: {reason}: {raw}")
                if not raw.endswith("\n"):
                    out.write("\n")

    return stats, invalid_rows


def load_jsonl_stats(
    path: str,
    invalid_path: str | None = None,
    *,
    allow_legacy: bool = False,
    require_schema_version: str | None = None,
) -> dict[str, Any]:
    """Load JSONL stats or exit with a clear validation message."""
    stats, invalid_rows = collect_jsonl_stats(
        path,
        invalid_path,
        allow_legacy=allow_legacy,
        require_schema_version=require_schema_version,
    )
    if invalid_rows:
        if invalid_path:
            sys.exit(f"Schema validation found invalid JSONL rows in {path}: {invalid_path}")
        line_no, reason, _ = invalid_rows[0]
        sys.exit(f"Invalid JSONL row in {path}:{line_no}: {reason}")
    return stats


def iter_jsonl_targets(path: str) -> Any:
    """Yield JSONL file targets from a file or directory path."""
    if os.path.isdir(path):
        for name in sorted(os.listdir(path)):
            if name.endswith(".jsonl"):
                yield os.path.join(path, name)
        return
    yield path


def main() -> None:
    """CLI entry point for CAE JSONL validation."""
    parser = argparse.ArgumentParser(description="Validate CAE JSONL logs")
    parser.add_argument("paths", nargs="+", help="JSONL file(s) or directories to validate")
    parser.add_argument("--invalid-report", help="Write invalid rows to this file")
    parser.add_argument(
        "--require-schema-version",
        choices=[SCHEMA_VERSION],
        help="Require every structured row to use this schema",
    )
    parser.add_argument("--strict", action="store_true", help="Accepted for interface stability")
    args = parser.parse_args()

    all_invalid_rows: list[tuple[str, int, str, str]] = []
    validated_files = 0

    for input_path in args.paths:
        targets = list(iter_jsonl_targets(input_path))
        if not targets:
            sys.exit(f"No JSONL files found in {input_path}")
        for target in targets:
            if not os.path.isfile(target):
                sys.exit(f"Path is not a file: {target}")
            validated_files += 1
            _, invalid_rows = collect_jsonl_stats(
                target,
                require_schema_version=args.require_schema_version,
            )
            all_invalid_rows.extend((target, line_no, reason, raw) for line_no, reason, raw in invalid_rows)

    if args.invalid_report:
        with open(args.invalid_report, "w", encoding="utf-8") as out:
            for target, line_no, reason, raw in all_invalid_rows:
                out.write(f"{target}:{line_no}: {reason}: {raw}")
                if not raw.endswith("\n"):
                    out.write("\n")

    if all_invalid_rows:
        sys.exit(f"Validation failed: {len(all_invalid_rows)} invalid row(s) across {validated_files} file(s)")

    print(f"Validated {validated_files} JSONL file(s) successfully.")


if __name__ == "__main__":
    main()
