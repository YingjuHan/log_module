#!/usr/bin/env python3
"""Compatibility dispatcher for CAE report and verification tools."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    """Dispatch legacy report.py subcommands to package modules."""
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "generate":
        from tools.reporting.generate_reports import main as generate_main

        sys.argv.pop(1)
        generate_main()
        return 0
    if command == "postprocess":
        from tools.reporting.run_postprocess_report import main as postprocess_main

        sys.argv.pop(1)
        postprocess_main()
        return 0
    if command == "verify":
        from tools.verify.verify_cae_pipeline import main as verify_main

        sys.argv.pop(1)
        verify_main()
        return 0
    if command == "e2e":
        from tools.verify.e2e_verify import main as e2e_main

        sys.argv.pop(1)
        e2e_main()
        return 0
    if command == "parity":
        from tools.verify.verify_goaccess_parity import main as parity_main

        sys.argv.pop(1)
        parity_main()
        return 0

    print("Usage: report.py {generate|postprocess|verify|e2e|parity} [options]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
