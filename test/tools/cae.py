#!/usr/bin/env python3
"""Single-entry CLI for CAE test tooling."""

from __future__ import annotations

import os
import sys
from pathlib import Path
import subprocess


TOOLS_DIR = Path(__file__).resolve().parent
TEST_ROOT = TOOLS_DIR.parent
COMMANDS = {
    "run",
    "merge",
    "report",
    "verify",
    "cleanup",
    "tail",
    "validate",
    "summary",
    "summarize",
    "parity",
}


def run_python(args: list[str]) -> int:
    """Run a Python child command and return its exit code."""
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(TEST_ROOT) if not python_path else f"{TEST_ROOT}{os.pathsep}{python_path}"
    return int(
        subprocess.run(
            [sys.executable, *args],
            check=False,
            cwd=str(TEST_ROOT),
            env=env,
        ).returncode
    )


def run_module(module_name: str, args: list[str]) -> int:
    """Run a tools package module."""
    return run_python(["-m", module_name, *args])


def print_usage() -> None:
    """Print concise command help."""
    print(
        "Usage: python -m tools.cae [entry-options] "
        "{run|merge|report|verify|cleanup|tail|validate|summary|parity} [options]",
        file=sys.stderr,
    )


def normalize_entry_args(args: list[str]) -> list[str]:
    """Allow entry-level options before the command and forward them to it."""
    if not args or args[0] in COMMANDS:
        return args

    for index, token in enumerate(args):
        if token in COMMANDS:
            return [token, *args[:index], *args[index + 1:]]
    return args


def main(argv: list[str] | None = None) -> int:
    """Dispatch high-level CAE commands to package modules or build scripts."""
    args = normalize_entry_args(list(sys.argv[1:] if argv is None else argv))
    if not args:
        print_usage()
        return 2

    command = args.pop(0)
    if command == "run":
        return run_module("tools.runtime.run_demo", args)
    if command == "merge":
        return run_module("tools.pipeline.merge_cae_logs", args)
    if command == "report":
        return run_module("tools.reporting.run_postprocess_report", args)
    if command == "verify":
        return run_module("tools.verify.e2e_verify", args)
    if command == "cleanup":
        return run_module("tools.runtime.cleanup_cae_logs", args)
    if command == "tail":
        return run_module("tools.pipeline.cae_tail", args)
    if command == "validate":
        return run_module("tools.pipeline.validate_cae_events", args)
    if command in {"summary", "summarize"}:
        return run_module("tools.reporting.summarize_cae_report", args)
    if command == "parity":
        return run_module("tools.verify.verify_goaccess_parity", args)

    print_usage()
    return 2


if __name__ == "__main__":
    sys.exit(main())
