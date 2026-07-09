#!/usr/bin/env python3
"""Flatten a JSONL/NDJSON file into CSV for table viewers such as Tad.

Usage:
  python3 jsonl_to_csv_flat.py input.jsonl output.csv
"""
import csv
import json
import sys
from collections import OrderedDict
from pathlib import Path

PREFERRED_PREFIX = [
    "timestamp", "date", "time", "component", "stage", "action", "level",
    "event_kind", "duration_us", "duration_ms", "size", "session", "mpi_rank",
    "source", "thread_name", "sequence", "trace_id", "span_id", "parent_span_id",
    "object_type", "object_name", "result", "reason", "message",
]


def flatten(obj, prefix=""):
    """Flatten nested dict/list values using dot notation."""
    out = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_key = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                out.update(flatten(value, new_key))
            elif isinstance(value, list):
                # Keep arrays as compact JSON strings; this avoids exploding rows.
                out[new_key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            else:
                out[new_key] = value
    else:
        out[prefix or "value"] = obj
    return out


def normalized_row(flat):
    # Add a human-friendly millisecond column while keeping original duration_us.
    if "duration_us" in flat and flat.get("duration_us") not in (None, ""):
        try:
            flat["duration_ms"] = round(float(flat["duration_us"]) / 1000.0, 3)
        except Exception:
            flat["duration_ms"] = ""
    else:
        flat.setdefault("duration_ms", "")
    return flat


def read_flat_rows(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON at line {line_no}: {exc}")
            yield normalized_row(flatten(obj))


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python3 jsonl_to_csv_flat.py input.jsonl output.csv")

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    # First pass: discover all columns safely, even if fields appear late in the file.
    columns = OrderedDict()
    row_count = 0
    for row in read_flat_rows(input_path):
        row_count += 1
        for key in row.keys():
            columns.setdefault(key, None)

    discovered = list(columns.keys())
    preferred = [c for c in PREFERRED_PREFIX if c in columns]
    remaining = sorted([c for c in discovered if c not in preferred])
    fieldnames = preferred + remaining

    # Second pass: write CSV.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in read_flat_rows(input_path):
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print(f"Wrote {row_count} rows and {len(fieldnames)} columns to {output_path}")


if __name__ == "__main__":
    main()
