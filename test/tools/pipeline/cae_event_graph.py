#!/usr/bin/env python3
"""Build DAG, timeline, and MPI heatmap artifacts from enriched CAE events."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


OBSERVABILITY_SCHEMA_VERSION = "cae_observability_v1"

NODE_COLUMNS = (
    "event_id",
    "parent_event_id",
    "job_id",
    "trace_id",
    "node_id",
    "mpi_rank",
    "event_type",
    "phase",
    "timestamp_epoch_us",
    "logical_time",
    "component",
    "action",
)

EDGE_COLUMNS = (
    "source_event_id",
    "target_event_id",
    "edge_type",
    "job_id",
    "trace_id",
    "node_id",
    "mpi_rank",
)

HEATMAP_COLUMNS = (
    "job_id",
    "node_id",
    "mpi_rank",
    "time_bucket_ms",
    "event_count",
    "span_count",
    "duration_us_sum",
)


def _string(value: object) -> str:
    return "" if value is None else str(value)


def _integer(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _node_identity(event: dict[str, Any], index: int, warnings: list[dict[str, object]]) -> str:
    event_id = _string(event.get("event_id"))
    if event_id:
        return event_id
    global_sequence_id = _string(event.get("global_sequence_id"))
    warnings.append(
        {
            "code": "incomplete_graph_identity",
            "message": "event_id is missing; using global_sequence_id fallback",
            "row_index": index,
            "global_sequence_id": global_sequence_id,
        }
    )
    return global_sequence_id or f"row:{index}"


def _ordering_key(node: dict[str, Any]) -> tuple[object, ...]:
    return (
        _integer(node.get("sequence")),
        _integer(node.get("logical_time")),
        _integer(node.get("timestamp_epoch_us")),
        _string(node.get("node_id")),
        _string(node.get("mpi_rank")),
        _integer(node.get("_index")),
    )


def _timeline_key(node: dict[str, Any]) -> tuple[object, ...]:
    return (
        _integer(node.get("timestamp_epoch_us")),
        _integer(node.get("logical_time")),
        _string(node.get("node_id")),
        _string(node.get("mpi_rank")),
        _integer(node.get("sequence")),
        _integer(node.get("_index")),
    )


def _warn_inversion(
    warnings: list[dict[str, object]],
    edge_type: str,
    source: dict[str, Any],
    target: dict[str, Any],
) -> None:
    source_ts = _integer(source.get("timestamp_epoch_us"))
    target_ts = _integer(target.get("timestamp_epoch_us"))
    source_logical = _integer(source.get("logical_time"))
    target_logical = _integer(target.get("logical_time"))
    if target_ts < source_ts or target_logical < source_logical:
        warnings.append(
            {
                "code": f"{edge_type}_inversion",
                "message": "timestamp_epoch_us or logical_time decreased across a derived sequence edge",
                "source_event_id": source["event_id"],
                "target_event_id": target["event_id"],
                "edge_type": edge_type,
            }
        )


def _edge(edge_type: str, source: dict[str, Any], target: dict[str, Any]) -> dict[str, object]:
    return {
        "source_event_id": source["event_id"],
        "target_event_id": target["event_id"],
        "edge_type": edge_type,
        "job_id": target.get("job_id"),
        "trace_id": target.get("trace_id"),
        "node_id": target.get("node_id"),
        "mpi_rank": target.get("mpi_rank"),
    }


def _make_node(event: dict[str, Any], event_id: str, index: int) -> dict[str, object]:
    node = {column: event.get(column) for column in NODE_COLUMNS}
    node["event_id"] = event_id
    node["sequence"] = event.get("sequence")
    node["duration_us"] = event.get("duration_us", 0)
    node["event_kind"] = event.get("event_kind")
    node["_index"] = index
    return node


def _public_node(node: dict[str, object]) -> dict[str, object]:
    return {column: node.get(column) for column in NODE_COLUMNS}


def _rank_key(node: dict[str, Any]) -> tuple[str, str, str]:
    return (_string(node.get("job_id")), _string(node.get("node_id")), _string(node.get("mpi_rank")))


def build_observability_artifacts(events: list[dict[str, Any]], *, bucket_ms: int = 1000) -> dict[str, object]:
    """Build derived observability artifacts from enriched CAE events."""
    if bucket_ms <= 0:
        raise ValueError(f"bucket_ms must be positive, got {bucket_ms}")

    warnings: list[dict[str, object]] = []
    nodes_internal: list[dict[str, object]] = []
    first_by_event_id: dict[str, dict[str, object]] = {}
    seen_event_ids: set[str] = set()

    for index, event in enumerate(events):
        event_id = _node_identity(event, index, warnings)
        if event_id in seen_event_ids:
            warnings.append(
                {
                    "code": "duplicate_event_id",
                    "message": "event_id appears more than once",
                    "event_id": event_id,
                    "row_index": index,
                }
            )
        seen_event_ids.add(event_id)
        node = _make_node(event, event_id, index)
        nodes_internal.append(node)
        first_by_event_id.setdefault(event_id, node)

    edges: list[dict[str, object]] = []
    for node in nodes_internal:
        parent_event_id = _string(node.get("parent_event_id"))
        if not parent_event_id:
            continue
        parent = first_by_event_id.get(parent_event_id)
        if parent is None:
            warnings.append(
                {
                    "code": "missing_parent_event",
                    "message": "parent_event_id does not exist in this event set",
                    "event_id": node["event_id"],
                    "parent_event_id": parent_event_id,
                }
            )
            continue
        if _string(parent.get("job_id")) != _string(node.get("job_id")):
            warnings.append(
                {
                    "code": "cross_job_parent_edge",
                    "message": "parent_event_id points to an event with a different job_id",
                    "event_id": node["event_id"],
                    "parent_event_id": parent_event_id,
                    "job_id": node.get("job_id"),
                    "parent_job_id": parent.get("job_id"),
                }
            )
        edges.append(_edge("parent", parent, node))

    grouped_by_trace: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    grouped_by_rank: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for node in nodes_internal:
        trace_id = _string(node.get("trace_id"))
        if trace_id:
            grouped_by_trace[(_string(node.get("job_id")), trace_id)].append(node)
        grouped_by_rank[_rank_key(node)].append(node)

    for group in grouped_by_trace.values():
        ordered = sorted(group, key=_ordering_key)
        for source, target in zip(ordered, ordered[1:]):
            _warn_inversion(warnings, "trace_sequence", source, target)
            edges.append(_edge("trace_sequence", source, target))

    for group in grouped_by_rank.values():
        ordered = sorted(group, key=_ordering_key)
        for source, target in zip(ordered, ordered[1:]):
            _warn_inversion(warnings, "rank_sequence", source, target)
            edges.append(_edge("rank_sequence", source, target))

    bucket_us = bucket_ms * 1000
    heatmap_accumulator: dict[tuple[str, str, str, int], dict[str, object]] = {}
    for node in nodes_internal:
        bucket = (_integer(node.get("timestamp_epoch_us")) // bucket_us) * bucket_ms
        rank_value = node.get("mpi_rank")
        key = (_string(node.get("job_id")), _string(node.get("node_id")), "" if rank_value is None else rank_value, bucket)
        row = heatmap_accumulator.setdefault(
            key,
            {
                "job_id": key[0],
                "node_id": key[1],
                "mpi_rank": key[2],
                "time_bucket_ms": bucket,
                "event_count": 0,
                "span_count": 0,
                "duration_us_sum": 0,
            },
        )
        row["event_count"] = _integer(row["event_count"]) + 1
        if node.get("event_kind") == "span":
            row["span_count"] = _integer(row["span_count"]) + 1
            row["duration_us_sum"] = _integer(row["duration_us_sum"]) + _integer(node.get("duration_us"))

    nodes = [_public_node(node) for node in sorted(nodes_internal, key=_timeline_key)]
    timeline = {
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "bucket_ms": bucket_ms,
        "events": nodes,
        "edges": edges,
    }
    heatmap_rows = [
        heatmap_accumulator[key]
        for key in sorted(heatmap_accumulator, key=lambda item: (item[0], item[1], str(item[2]), item[3]))
    ]
    stats = summarize_observability(nodes_internal, edges, warnings)
    report = {
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "stats": stats,
        "warnings": warnings,
    }
    return {
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "nodes": nodes,
        "edges": edges,
        "timeline": timeline,
        "heatmap_rows": heatmap_rows,
        "warnings": warnings,
        "stats": stats,
        "report": report,
    }


def summarize_observability(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, object]],
    warnings: list[dict[str, object]],
) -> dict[str, object]:
    """Summarize graph health and rank-local event distribution."""
    per_rank_counts: dict[str, int] = defaultdict(int)
    grouped_by_rank: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        rank_tuple = _rank_key(node)
        rank_label = ":".join(rank_tuple)
        per_rank_counts[rank_label] += 1
        grouped_by_rank[rank_tuple].append(node)

    max_rank_gap = 0
    for group in grouped_by_rank.values():
        ordered = sorted(group, key=lambda node: (_integer(node.get("timestamp_epoch_us")), _integer(node.get("_index"))))
        for source, target in zip(ordered, ordered[1:]):
            gap = _integer(target.get("timestamp_epoch_us")) - _integer(source.get("timestamp_epoch_us"))
            if gap > max_rank_gap:
                max_rank_gap = gap

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "orphan_count": sum(1 for warning in warnings if warning.get("code") == "missing_parent_event"),
        "warning_count": len(warnings),
        "per_rank_event_counts": dict(sorted(per_rank_counts.items())),
        "max_rank_local_gap_us": max_rank_gap,
    }


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fieldnames})


def write_observability_artifacts(output_dir: Path | str, prefix: str, artifacts: dict[str, object]) -> dict[str, Path]:
    """Write observability artifacts beside the tabular export outputs."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "dag_nodes": target_dir / f"{prefix}_dag_nodes.csv",
        "dag_edges": target_dir / f"{prefix}_dag_edges.csv",
        "timeline": target_dir / f"{prefix}_timeline.json",
        "rank_heatmap": target_dir / f"{prefix}_rank_heatmap.csv",
        "observability_report": target_dir / f"{prefix}_observability_report.json",
    }
    _write_csv(paths["dag_nodes"], NODE_COLUMNS, list(artifacts["nodes"]))
    _write_csv(paths["dag_edges"], EDGE_COLUMNS, list(artifacts["edges"]))
    _write_csv(paths["rank_heatmap"], HEATMAP_COLUMNS, list(artifacts["heatmap_rows"]))
    paths["timeline"].write_text(json.dumps(artifacts["timeline"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["observability_report"].write_text(json.dumps(artifacts["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return paths
