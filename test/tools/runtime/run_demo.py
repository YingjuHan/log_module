#!/usr/bin/env python3
"""Run one CAE demo executable multiple times without building it."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Callable

from tools.common.cae_env import CaeContext, ENV_APP_EXE, ENV_CONFIG_DIR, check_dir, check_file


def session_name(session_prefix: str, index: int) -> str:
    """Build a stable session/process name."""
    return f"{session_prefix}_{index}"


def run_demo_processes(
    *,
    app_exe: Path,
    cwd: Path,
    process_count: int,
    session_prefix: str,
    launcher: Callable[..., object] = subprocess.Popen,
) -> int:
    """Launch demo processes and return the first non-zero exit code."""
    resolved_app = check_file(app_exe, "Demo executable")
    resolved_cwd = check_dir(cwd, "Demo working directory")
    if process_count < 1:
        raise ValueError(f"process_count must be at least 1, got {process_count}")

    print(f"Launching {process_count} demo process(es) from {resolved_app}")
    processes: list[tuple[str, object]] = []
    for index in range(1, process_count + 1):
        name = session_name(session_prefix, index)
        print(f"  Starting [{name}]")
        process = launcher([str(resolved_app), name], cwd=str(resolved_cwd))
        processes.append((name, process))

    first_failure = 0
    for name, process in processes:
        wait = getattr(process, "wait")
        wait()
        return_code = int(getattr(process, "returncode"))
        if return_code == 0:
            print(f"  [{name}] completed successfully")
            continue
        print(f"  [{name}] failed with exit code {return_code}")
        if first_failure == 0:
            first_failure = return_code or 1

    return first_failure


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    context = CaeContext.create(repo_paths=None)
    parser = argparse.ArgumentParser(description="Run a CAE demo executable without building it")
    parser.add_argument("--manifest", default=str(context.manifest_path), help="Optional manifest JSON")
    parser.add_argument("--app-exe", default=None, help="Demo executable path")
    parser.add_argument("--cwd", default=None, help="Working directory for the demo process")
    parser.add_argument("--process-count", type=int, default=3, help="Number of concurrent processes")
    parser.add_argument("--session-prefix", default="Proc", help="Prefix used for per-process sessions")
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        context = CaeContext.create(manifest_path=args.manifest)
        app_exe = context.path_value(
            cli_value=args.app_exe,
            env_var=ENV_APP_EXE,
            manifest_keys=("app", "exe"),
            default=context.repo_paths.app_exe,
        )
        cwd = context.path_value(
            cli_value=args.cwd,
            env_var=ENV_CONFIG_DIR,
            manifest_keys=("app", "config_dir"),
            default=context.repo_paths.app_config_dir,
        )
        if app_exe is None or cwd is None:
            raise ValueError("app_exe and cwd must resolve to real paths")

        return_code = run_demo_processes(
            app_exe=app_exe,
            cwd=cwd,
            process_count=args.process_count,
            session_prefix=args.session_prefix,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        sys.exit(str(exc))

    sys.exit(return_code)


if __name__ == "__main__":
    main()
