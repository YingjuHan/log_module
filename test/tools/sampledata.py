#!/usr/bin/env python3
"""Compatibility entry point for running sample demos and CTest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.common.cae_env import CaeContext, ENV_APP_BUILD_DIR, run_checked
from tools.runtime.run_demo import run_demo_processes


def run_ctest(*, build_dir: Path, config: str = "Debug", output_on_failure: bool = False) -> None:
    """Run CTest in a sample build directory."""
    cmd = ["ctest", "--test-dir", str(build_dir), "--build-config", config]
    if output_on_failure:
        cmd.append("--output-on-failure")
    run_checked(cmd)


def cli_demo() -> None:
    """Run the sample demo executable."""
    from tools.runtime.run_demo import main

    main()


def cli_ctest() -> None:
    """Run sample CTest cases."""
    context = CaeContext.create(repo_paths=None)
    parser = argparse.ArgumentParser(description="Run sample CTest cases without rebuilding")
    parser.add_argument("--manifest", default=str(context.manifest_path), help="Optional manifest JSON")
    parser.add_argument("--build-dir", default=None, help="Sample build directory")
    parser.add_argument("--config", choices=["Debug", "Release"], default="Debug")
    parser.add_argument("--output-on-failure", action="store_true")
    args = parser.parse_args()

    try:
        context = CaeContext.create(manifest_path=args.manifest)
        build_dir = context.path_value(
            cli_value=args.build_dir,
            env_var=ENV_APP_BUILD_DIR,
            manifest_keys=("app", "build_dir"),
            default=context.repo_paths.app_build_dir,
        )
        if build_dir is None:
            raise ValueError("build_dir must resolve to a real path")
        run_ctest(build_dir=build_dir, config=args.config, output_on_failure=args.output_on_failure)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "ctest":
        sys.argv.pop(1)
        cli_ctest()
    else:
        cli_demo()
