#!/usr/bin/env python3
"""Compatibility dispatcher for CAE processing tools."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    """Dispatch legacy process.py subcommands to package modules."""
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "merge":
        from tools.pipeline.merge_cae_logs import main as merge_main

        sys.argv.pop(1)
        merge_main()
        return 0
    if command == "validate":
        from tools.pipeline.validate_cae_events import main as validate_main

        sys.argv.pop(1)
        validate_main()
        return 0
    if command in {"summarize", "summary"}:
        from tools.reporting.summarize_cae_report import main as summary_main

        sys.argv.pop(1)
        summary_main()
        return 0
    if command == "cleanup":
        from tools.runtime.cleanup_cae_logs import main as cleanup_main

        sys.argv.pop(1)
        cleanup_main()
        return 0
    if command == "tail":
        from tools.pipeline.cae_tail import main as tail_main

        sys.argv.pop(1)
        tail_main()
        return 0

    print("Usage: process.py {merge|validate|summarize|cleanup|tail} [options]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
