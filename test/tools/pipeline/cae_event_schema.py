#!/usr/bin/env python3
"""Shared CAE event schema v1 constants for Python tooling."""

from __future__ import annotations

import json
from pathlib import Path


SCHEMA_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config" / "cae_event_schema_v1.json"


_FALLBACK_REGISTRY = {
    "schema_version": "cae_event_v1",
    "required_string_fields": [
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
        "schema_version",
        "event_id",
        "event_type",
        "phase",
        "domain",
        "entity_type",
        "entity_name",
        "job_id",
        "global_sequence_id",
    ],
    "required_integer_fields": [
        "duration_us",
        "size",
        "sequence",
        "logical_time",
        "timestamp_epoch_us",
        "monotonic_us",
    ],
    "nullable_string_fields": [
        "parent_span_id",
        "parent_event_id",
        "object_type",
        "object_name",
        "result",
        "reason",
    ],
    "enums": {
        "event_type": [
            "geometry",
            "mesh",
            "solve",
            "io",
            "ui",
            "mpi",
            "postprocess",
            "system",
            "unknown",
        ],
        "phase": [
            "start",
            "progress",
            "end",
            "unknown",
        ],
        "domain": [
            "cfd",
            "fem",
            "pre",
            "post",
            "system",
            "unknown",
        ],
    },
    "export_columns": [
        "schema_version",
        "timestamp",
        "timestamp_epoch_us",
        "monotonic_us",
        "date",
        "time",
        "source",
        "component",
        "stage",
        "action",
        "level",
        "message",
        "event_kind",
        "event_type",
        "phase",
        "domain",
        "entity_type",
        "entity_name",
        "duration_us",
        "size",
        "session",
        "job_id",
        "thread_name",
        "node_id",
        "mpi_rank",
        "sequence",
        "global_sequence_id",
        "logical_time",
        "trace_id",
        "span_id",
        "event_id",
        "parent_span_id",
        "parent_event_id",
        "object_type",
        "object_name",
        "result",
        "reason",
        "call_chain_status",
    ],
}


def load_schema_registry(path: Path | str = SCHEMA_REGISTRY_PATH) -> dict[str, object]:
    """Load the authoritative CAE event schema registry."""
    registry_path = Path(path)
    if not registry_path.is_file():
        return dict(_FALLBACK_REGISTRY)
    with registry_path.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(f"Schema registry must be a JSON object: {registry_path}")
    return payload


SCHEMA_REGISTRY = load_schema_registry()
SCHEMA_VERSION = str(SCHEMA_REGISTRY.get("schema_version", _FALLBACK_REGISTRY["schema_version"]))


def _string_tuple(key: str, fallback: tuple[str, ...] = ()) -> tuple[str, ...]:
    values = SCHEMA_REGISTRY.get(key)
    if isinstance(values, list) and all(isinstance(value, str) for value in values):
        return tuple(values)
    return fallback


def _enum_set(key: str, fallback: set[str]) -> set[str]:
    enums = SCHEMA_REGISTRY.get("enums")
    if not isinstance(enums, dict):
        return fallback
    values = enums.get(key)
    if isinstance(values, list) and all(isinstance(value, str) for value in values):
        return set(values)
    return fallback

EVENT_TYPES = {
    "geometry",
    "mesh",
    "solve",
    "io",
    "ui",
    "mpi",
    "postprocess",
    "system",
    "unknown",
}
EVENT_TYPES = _enum_set("event_type", EVENT_TYPES)

EVENT_PHASES = {
    "start",
    "progress",
    "end",
    "unknown",
}
EVENT_PHASES = _enum_set("phase", EVENT_PHASES)

DOMAINS = {
    "cfd",
    "fem",
    "pre",
    "post",
    "system",
    "unknown",
}
DOMAINS = _enum_set("domain", DOMAINS)

_registry_required_strings = _string_tuple("required_string_fields")
_registry_required_integers = _string_tuple("required_integer_fields")
_registry_nullable_strings = _string_tuple("nullable_string_fields")

_v1_required_string_fields = ("schema_version",) + tuple(
    field for field in _registry_required_strings if field != "schema_version"
)

V1_REQUIRED_STRING_FIELDS = _v1_required_string_fields

V1_REQUIRED_INTEGER_FIELDS = _registry_required_integers or (
    "duration_us",
    "size",
    "sequence",
    "logical_time",
    "timestamp_epoch_us",
    "monotonic_us",
)

V1_NULLABLE_STRING_FIELDS = _registry_nullable_strings or (
    "parent_span_id",
    "parent_event_id",
    "object_type",
    "object_name",
    "result",
    "reason",
)

BASE_EXPORT_COLUMNS = _string_tuple("export_columns", _FALLBACK_REGISTRY["export_columns"])
METRIC_COLUMN_PREFIX = str(SCHEMA_REGISTRY.get("metric_column_prefix", "metric_"))
