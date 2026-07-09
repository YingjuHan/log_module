#!/usr/bin/env python3
"""Unified CAE log workflow orchestrator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.pipeline.export_cae_events import export_cae_events
from tools.pipeline.merge_cae_logs import merge_cae_logs
from tools.pipeline.validate_cae_config import validate_config
from tools.pipeline.validate_cae_events import SCHEMA_VERSION, collect_jsonl_stats


TEST_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = TEST_ROOT.parent / "cae_log_module"


def validate_events(path: Path, *, require_schema_version: bool) -> int:
    _, invalid_rows = collect_jsonl_stats(
        str(path),
        require_schema_version=SCHEMA_VERSION if require_schema_version else None,
    )
    if invalid_rows:
        line_no, reason, _ = invalid_rows[0]
        raise ValueError(f"Invalid CAE JSONL row in {path}:{line_no}: {reason}")
    with path.open(encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def run_pipeline(
    *,
    config_file: Path,
    input_log: Path | None,
    input_dir: Path | None,
    output_log: Path | None,
    output_dir: Path,
    prefix: str,
    require_schema_version: bool,
    require_columnar: bool,
    observability: bool,
) -> dict[str, object]:
    config_report = validate_config(config_file)
    if not config_report["valid"]:
        raise ValueError("Invalid CAE logger config: " + "; ".join(config_report["errors"]))

    source_log = input_log
    merge_result: dict[str, object] | None = None
    if input_dir is not None:
        if output_log is None:
            output_log = output_dir / "cae_events.jsonl"
        merge_result = merge_cae_logs(input_dir=input_dir, output_log=output_log)
        source_log = Path(merge_result["output_log"])

    if source_log is None:
        raise ValueError("Either --input-log or --input-dir must be provided")
    if not source_log.is_file():
        raise FileNotFoundError(f"CAE JSONL input log not found: {source_log}")

    line_count = validate_events(source_log, require_schema_version=require_schema_version)
    export_result = export_cae_events(
        source_log,
        output_dir,
        prefix=prefix,
        require_columnar=require_columnar,
        observability=observability,
    )
    return {
        "config": config_report,
        "source_log": source_log.resolve(strict=False),
        "line_count": line_count,
        "merge": merge_result,
        "export": export_result,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate, optionally merge, and export CAE event logs")
    parser.add_argument("--config-file", default=str(MODULE_ROOT / "config" / "cae_logger_config.ini"))
    parser.add_argument("--input-log", default=None, help="Existing JSONL log to validate/export")
    parser.add_argument("--input-dir", default=None, help="Directory containing cae_events*.jsonl fragments to merge first")
    parser.add_argument("--output-log", default=None, help="Merged JSONL output when --input-dir is used")
    parser.add_argument("--output-dir", default=str(TEST_ROOT / "out" / "reports"), help="Output directory for exported artifacts")
    parser.add_argument("--prefix", default="cae_events", help="Export artifact prefix")
    parser.add_argument("--allow-legacy", action="store_true", help="Do not require schema_version=cae_event_v1")
    parser.add_argument("--require-columnar", action="store_true", help="Fail unless Arrow/Parquet outputs are written")
    parser.add_argument("--observability", action="store_true", help="Write DAG, timeline, rank heatmap, and report artifacts")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        result = run_pipeline(
            config_file=Path(args.config_file),
            input_log=Path(args.input_log) if args.input_log else None,
            input_dir=Path(args.input_dir) if args.input_dir else None,
            output_log=Path(args.output_log) if args.output_log else None,
            output_dir=Path(args.output_dir),
            prefix=args.prefix,
            require_schema_version=not args.allow_legacy,
            require_columnar=args.require_columnar,
            observability=args.observability,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        sys.exit(str(exc))

    print(f"Validated config: {result['config']['config_file']}")
    if result["merge"] is not None:
        print(f"Merged log: {result['source_log']}")
    print(f"Validated CAE events: {result['line_count']}")
    export = result["export"]
    print(f"Wrote {export['schema_path']}")
    print(f"Wrote {export['csv_path']}")
    print(export["columnar_message"])


if __name__ == "__main__":
    main()
