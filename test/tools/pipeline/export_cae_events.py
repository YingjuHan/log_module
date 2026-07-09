#!/usr/bin/env python3
"""Export CAE JSONL events to TAD-friendly tabular files."""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import sys
from pathlib import Path
from typing import Any

from tools.pipeline.cae_event_graph import build_observability_artifacts, write_observability_artifacts
from tools.pipeline.cae_event_schema import BASE_EXPORT_COLUMNS, METRIC_COLUMN_PREFIX, SCHEMA_VERSION
from tools.pipeline.cae_event_view import load_validated_events

_DEFAULT_PYARROW = object()


def flatten_event(event: dict[str, Any], metric_keys: list[str], *, missing_value: object = "") -> dict[str, Any]:
    row: dict[str, Any] = {}
    for column in BASE_EXPORT_COLUMNS:
        value = event.get(column)
        row[column] = missing_value if value is None else value
    metrics = event.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    for key in metric_keys:
        value = metrics.get(key)
        row[f"{METRIC_COLUMN_PREFIX}{key}"] = missing_value if value is None else value
    return row


def load_pyarrow(pyarrow_module: object = _DEFAULT_PYARROW) -> object | None:
    if pyarrow_module is not _DEFAULT_PYARROW:
        return pyarrow_module
    try:
        pa = importlib.import_module("pyarrow")
        feather = importlib.import_module("pyarrow.feather")
        parquet = importlib.import_module("pyarrow.parquet")
        setattr(pa, "feather", feather)
        setattr(pa, "parquet", parquet)
        return pa
    except ImportError:
        return None


def write_schema(path: Path, columns: list[str], metric_keys: list[str]) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "format": "cae_event_table_v1",
        "columns": columns,
        "metric_columns": [f"{METRIC_COLUMN_PREFIX}{key}" for key in metric_keys],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export_cae_events(
    input_path: Path | str,
    output_dir: Path | str,
    *,
    prefix: str = "cae_events",
    require_columnar: bool = False,
    observability: bool = False,
    pyarrow_module: object = _DEFAULT_PYARROW,
) -> dict[str, object]:
    source = Path(input_path)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    events = load_validated_events(str(source))
    metric_keys = sorted(
        {
            str(key)
            for event in events
            if isinstance(event.get("metrics"), dict)
            for key in event["metrics"].keys()
        }
    )
    columns = list(BASE_EXPORT_COLUMNS) + [f"{METRIC_COLUMN_PREFIX}{key}" for key in metric_keys]
    rows = [flatten_event(event, metric_keys) for event in events]
    columnar_rows = [flatten_event(event, metric_keys, missing_value=None) for event in events]

    schema_path = target_dir / f"{prefix}_schema.json"
    csv_path = target_dir / f"{prefix}.csv"
    arrow_path = target_dir / f"{prefix}.arrow"
    parquet_path = target_dir / f"{prefix}.parquet"

    write_schema(schema_path, columns, metric_keys)
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    pa = load_pyarrow(pyarrow_module)
    columnar_written = False
    columnar_message = "pyarrow is not installed; Arrow and Parquet outputs were skipped."
    if pa is not None:
        table = pa.Table.from_pylist(columnar_rows)
        pa.feather.write_feather(table, arrow_path)
        pa.parquet.write_table(table, parquet_path)
        columnar_written = True
        columnar_message = "Arrow and Parquet outputs written."
    elif require_columnar:
        raise RuntimeError("pyarrow is required to write Arrow/Parquet outputs. Install pyarrow or omit --require-columnar.")

    result = {
        "rows": len(rows),
        "schema_path": schema_path,
        "csv_path": csv_path,
        "arrow_path": arrow_path if columnar_written else None,
        "parquet_path": parquet_path if columnar_written else None,
        "columnar_written": columnar_written,
        "columnar_message": columnar_message,
    }
    if observability:
        artifacts = build_observability_artifacts(events)
        result["observability_paths"] = write_observability_artifacts(target_dir, prefix, artifacts)
        result["observability_report"] = artifacts["report"]
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export CAE JSONL events to CSV and optional Arrow/Parquet")
    parser.add_argument("--input", default=str(Path("logs") / "cae_events.jsonl"), help="Input JSONL file or directory")
    parser.add_argument("--output-dir", default="reports", help="Output directory")
    parser.add_argument("--prefix", default="cae_events", help="Output filename prefix")
    parser.add_argument("--require-columnar", action="store_true", help="Fail if pyarrow is unavailable")
    parser.add_argument("--observability", action="store_true", help="Write DAG, timeline, rank heatmap, and observability report artifacts")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        result = export_cae_events(
            args.input,
            args.output_dir,
            prefix=args.prefix,
            require_columnar=args.require_columnar,
            observability=args.observability,
        )
    except (RuntimeError, SystemExit, ValueError) as exc:
        sys.exit(str(exc))
    print(f"Wrote {result['schema_path']}")
    print(f"Wrote {result['csv_path']}")
    for path in (result.get("observability_paths") or {}).values():
        print(f"Wrote {path}")
    print(result["columnar_message"])


if __name__ == "__main__":
    main()
