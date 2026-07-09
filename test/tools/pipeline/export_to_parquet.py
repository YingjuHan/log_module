#!/usr/bin/env python3
"""Export CAE JSONL events to CSV, Arrow IPC, and Parquet files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.pipeline.export_cae_events import export_cae_events


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export CAE JSONL events to CSV, Arrow, and Parquet")
    parser.add_argument("--input", default=str(Path("logs") / "cae_events.jsonl"))
    parser.add_argument("--output-dir", default="reports")
    parser.add_argument("--prefix", default="cae_events")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        result = export_cae_events(
            args.input,
            args.output_dir,
            prefix=args.prefix,
            require_columnar=True,
            observability=False,
        )
    except (RuntimeError, SystemExit, ValueError) as exc:
        sys.exit(str(exc))
    print(f"Wrote {result['schema_path']}")
    print(f"Wrote {result['csv_path']}")
    print(f"Wrote {result['arrow_path']}")
    print(f"Wrote {result['parquet_path']}")


if __name__ == "__main__":
    main()
