#!/usr/bin/env python3
"""Merge CAE event JSONL files and optionally copy module logs."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from tools.common.cae_env import CaeContext, ENV_LOGS_DIR, check_dir
from tools.pipeline.validate_cae_events import validate_jsonl_item


def find_event_logs(input_dir: Path) -> list[Path]:
    """Return sorted CAE event log fragments."""
    return sorted(path for path in input_dir.glob("cae_events*.jsonl") if path.is_file())


def find_module_logs(input_dir: Path) -> list[Path]:
    """Return sorted module log files produced by the demo."""
    return sorted(path for path in input_dir.glob("*.log") if path.is_file())


def _string_id(value: object) -> str:
    return value if isinstance(value, str) and value else ""


def causal_key(record: dict[str, object]) -> tuple[object, ...]:
    item = record["item"]
    assert isinstance(item, dict)

    def sort_value(value: object, default: object) -> object:
        return default if value is None else value

    return (
        sort_value(item.get("timestamp_epoch_us"), 0),
        sort_value(item.get("logical_time"), 0),
        sort_value(item.get("node_id"), ""),
        sort_value(item.get("mpi_rank"), -1),
        sort_value(item.get("source"), ""),
        sort_value(item.get("sequence"), 0),
        record["file_index"],
        record["line_no"],
    )


def align_parent_before_child(records: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Order records by causal key while forcing known parent events before children."""
    base_ordered = sorted(records, key=causal_key)
    base_position = {int(record["_merge_index"]): index for index, record in enumerate(base_ordered)}

    first_record_by_event_id: dict[str, dict[str, object]] = {}
    duplicate_event_ids: set[str] = set()
    for record in base_ordered:
        item = record["item"]
        assert isinstance(item, dict)
        event_id = _string_id(item.get("event_id")) or _string_id(item.get("span_id"))
        if not event_id:
            continue
        if event_id in first_record_by_event_id:
            duplicate_event_ids.add(event_id)
            continue
        first_record_by_event_id[event_id] = record

    children_by_parent: dict[int, list[int]] = defaultdict(list)
    indegree: dict[int, int] = {int(record["_merge_index"]): 0 for record in base_ordered}
    edge_count = 0
    for record in base_ordered:
        item = record["item"]
        assert isinstance(item, dict)
        parent_event_id = _string_id(item.get("parent_event_id")) or _string_id(item.get("parent_span_id"))
        if not parent_event_id:
            continue
        parent = first_record_by_event_id.get(parent_event_id)
        if parent is None:
            continue
        parent_index = int(parent["_merge_index"])
        child_index = int(record["_merge_index"])
        if parent_index == child_index:
            continue
        children_by_parent[parent_index].append(child_index)
        indegree[child_index] += 1
        edge_count += 1

    records_by_index = {int(record["_merge_index"]): record for record in base_ordered}
    ready = sorted(
        (index for index, count in indegree.items() if count == 0),
        key=lambda index: base_position[index],
    )
    ordered_indices: list[int] = []

    while ready:
        current = ready.pop(0)
        ordered_indices.append(current)
        for child in sorted(children_by_parent.get(current, []), key=lambda index: base_position[index]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
        ready.sort(key=lambda index: base_position[index])

    cycle_detected = len(ordered_indices) != len(base_ordered)
    if cycle_detected:
        ordered = [records_by_index[index] for index in ordered_indices]
        emitted = set(ordered_indices)
        ordered.extend(record for record in base_ordered if int(record["_merge_index"]) not in emitted)
    else:
        ordered = [records_by_index[index] for index in ordered_indices]

    base_indices = [int(record["_merge_index"]) for record in base_ordered]
    aligned_indices = [int(record["_merge_index"]) for record in ordered]
    stats = {
        "causal_parent_edges": edge_count,
        "causal_reordered": base_indices != aligned_indices,
        "duplicate_event_ids": sorted(duplicate_event_ids),
        "cycle_detected": cycle_detected,
    }
    return ordered, stats


def merge_cae_logs(
    *,
    input_dir: Path,
    output_log: Path,
    copy_module_logs_to: Path | None = None,
    preserve_file_order: bool = False,
) -> dict[str, object]:
    """Merge event logs and optionally copy module logs."""
    source_dir = check_dir(input_dir, "CAE log input directory")
    event_logs = find_event_logs(source_dir)
    if not event_logs:
        raise FileNotFoundError(f"No CAE event logs found in {source_dir} matching 'cae_events*.jsonl'")

    records: list[dict[str, object]] = []
    invalid_rows: list[str] = []
    merge_index = 0
    for file_index, event_log in enumerate(event_logs):
        with event_log.open(encoding="utf-8") as src:
            for line_no, raw in enumerate(src, 1):
                if not raw.strip():
                    continue
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as exc:
                    invalid_rows.append(f"{event_log}:{line_no}: invalid JSON: {exc}")
                    continue

                errors = validate_jsonl_item(parsed, allow_legacy=True)
                if errors:
                    invalid_rows.append(f"{event_log}:{line_no}: {'; '.join(errors)}")
                    continue

                assert isinstance(parsed, dict)

                records.append({
                    "raw": raw if raw.endswith("\n") else raw + "\n",
                    "item": parsed,
                    "file_index": file_index,
                    "line_no": line_no,
                    "source_file": str(event_log),
                    "_merge_index": merge_index,
                })
                merge_index += 1

    if invalid_rows:
        raise ValueError("Invalid CAE event log rows:\n" + "\n".join(invalid_rows[:10]))

    causal_stats: dict[str, object] = {
        "causal_parent_edges": 0,
        "causal_reordered": False,
        "duplicate_event_ids": [],
        "cycle_detected": False,
    }
    if preserve_file_order:
        ordered_records = records
    else:
        ordered_records, causal_stats = align_parent_before_child(records)

    output_log.parent.mkdir(parents=True, exist_ok=True)
    with output_log.open("w", encoding="utf-8") as out:
        for record in ordered_records:
            out.write(str(record["raw"]))
    total_lines = len(ordered_records)

    copied_logs: list[Path] = []
    if copy_module_logs_to is not None:
        target_dir = Path(copy_module_logs_to).resolve(strict=False)
        target_dir.mkdir(parents=True, exist_ok=True)
        for module_log in find_module_logs(source_dir):
            destination = target_dir / module_log.name
            shutil.copy2(module_log, destination)
            copied_logs.append(destination)

    report_path = output_log.with_suffix(".merge_report.json")
    merge_report = {
        "output_log": str(output_log.resolve(strict=False)),
        "ordering": "file" if preserve_file_order else "causal",
        "ordering_strategy": "file" if preserve_file_order else "parent_before_child_then_timestamp_logical_rank_sequence",
        "line_count": total_lines,
        "causal_parent_edges": causal_stats["causal_parent_edges"],
        "causal_reordered": causal_stats["causal_reordered"],
        "duplicate_event_ids": causal_stats["duplicate_event_ids"],
        "cycle_detected": causal_stats["cycle_detected"],
        "event_logs": [str(path.resolve(strict=False)) for path in event_logs],
    }
    report_path.write_text(json.dumps(merge_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "output_log": output_log.resolve(strict=False),
        "event_logs": [path.resolve(strict=False) for path in event_logs],
        "line_count": total_lines,
        "copied_logs": copied_logs,
        "ordering": merge_report["ordering"],
        "merge_report": report_path.resolve(strict=False),
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    context = CaeContext.create(repo_paths=None)
    parser = argparse.ArgumentParser(description="Merge CAE event logs without building or reporting")
    parser.add_argument("--manifest", default=str(context.manifest_path), help="Optional manifest JSON")
    parser.add_argument("--input-dir", default=None, help="Directory containing cae_events*.jsonl files")
    parser.add_argument("--output-log", default=None, help="Merged CAE JSONL output file")
    parser.add_argument("--copy-module-logs-to", default=None, help="Optional destination directory for *.log copies")
    parser.add_argument("--preserve-file-order", action="store_true", help="Concatenate fragments in filename order")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        context = CaeContext.create(manifest_path=args.manifest)
        input_dir = context.path_value(
            cli_value=args.input_dir,
            manifest_keys=("app", "config_dir"),
            default=context.repo_paths.app_config_dir,
        )
        if input_dir is None:
            raise ValueError("input_dir must resolve to a directory")
        if input_dir.name != "logs":
            input_dir = input_dir / "logs"

        if args.output_log:
            output_log = Path(args.output_log).expanduser().resolve(strict=False)
        else:
            logs_root = context.path_value(
                env_var=ENV_LOGS_DIR,
                manifest_keys=("logs_dir",),
                default=context.repo_paths.logs_dir,
            )
            if logs_root is None:
                raise ValueError("logs_dir must resolve to a directory")
            output_log = logs_root / "cae_events.jsonl"

        copy_dir = Path(args.copy_module_logs_to).expanduser().resolve(strict=False) if args.copy_module_logs_to else None

        result = merge_cae_logs(
            input_dir=input_dir,
            output_log=output_log,
            copy_module_logs_to=copy_dir,
            preserve_file_order=args.preserve_file_order,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        sys.exit(str(exc))

    print(f"Merged {len(result['event_logs'])} file(s) into {result['output_log']}")
    print(f"Total CAE events: {result['line_count']}")
    print(f"Ordering: {result['ordering']}")
    if result["copied_logs"]:
        print(f"Copied {len(result['copied_logs'])} module log(s)")


if __name__ == "__main__":
    main()
