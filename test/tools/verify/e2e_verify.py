#!/usr/bin/env python3
"""End-to-end verification for already built CAE artifacts."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from tools.common.cae_env import (
    ENV_GOACCESS_BUILD_DIR,
    ENV_GOACCESS_SOURCE_DIR,
    CaeContext,
    run_checked,
)
from tools.pipeline.merge_cae_logs import merge_cae_logs
from tools.runtime.run_demo import run_demo_processes
from tools.verify.verify_cae_pipeline import verify_cae_pipeline


def clean_output_tree(target_dir: Path, suffixes: set[str]) -> None:
    """Remove matching files and all nested directories from a target directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for entry in target_dir.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
            continue
        if entry.suffix in suffixes:
            entry.unlink()


def clean_build_logs(log_dir: Path) -> None:
    """Remove prior demo log fragments from the build output directory."""
    if not log_dir.is_dir():
        return
    for entry in log_dir.iterdir():
        if entry.is_file() and entry.suffix in {".log", ".jsonl"}:
            entry.unlink()


def launch_demo_quietly(args: list[str], cwd: str) -> subprocess.Popen[bytes]:
    """Launch a demo process without streaming sample logs into e2e stdout."""
    return subprocess.Popen(args, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def resolve_build_logs_dir(context: CaeContext) -> Path:
    """Resolve the sample logs directory from the actual app config directory."""
    config_dir = context.path_value(
        env_var="CAE_CONFIG_DIR",
        manifest_keys=("app", "config_dir"),
        default=context.repo_paths.app_config_dir,
    )
    if config_dir is None:
        raise ValueError("app config_dir must resolve to a directory")
    return config_dir if config_dir.name == "logs" else config_dir / "logs"


def resolve_cygwin_bash() -> str | None:
    """Locate a usable Cygwin bash executable for parity verification."""
    for env_name in ("CAE_CYGWIN_BASH", "CYGWIN_BASH"):
        value = os.environ.get(env_name)
        if value:
            candidate = Path(value).expanduser().resolve(strict=False)
            if candidate.is_file():
                return str(candidate)

    for candidate in (Path(r"D:\cygwin64\bin\bash.exe"), Path(r"C:\cygwin64\bin\bash.exe")):
        if candidate.is_file():
            return str(candidate)
    return None


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    context = CaeContext.create(repo_paths=None)
    parser = argparse.ArgumentParser(description="Run built CAE demo, merge logs, and verify reports")
    parser.add_argument("--manifest", default=str(context.manifest_path), help="Optional manifest JSON")
    parser.add_argument("--minimum-lines", type=int, default=1600, help="Minimum expected merged event count")
    parser.add_argument("--skip-probes", action="store_true", help="Skip synthetic verification probes")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the full already-built e2e verification flow."""
    args = build_parser().parse_args(argv)
    context = CaeContext.create(repo_paths=None, manifest_path=args.manifest)
    repo = context.repo_paths
    logs_dir = repo.logs_dir
    reports_dir = repo.reports_dir
    build_logs_dir = resolve_build_logs_dir(context)
    json_log = logs_dir / "cae_events.jsonl"
    parity_report = reports_dir / "goaccess_parity_report.txt"
    cygwin_bash = resolve_cygwin_bash()

    goaccess_exe = context.path_value(
        env_var="CAE_GOACCESS_EXE",
        manifest_keys=("goaccess", "exe"),
        default=repo.goaccess_exe,
    )
    app_exe = context.path_value(
        env_var="CAE_APP_EXE",
        manifest_keys=("app", "exe"),
        default=repo.app_exe,
    )
    config_dir = context.path_value(
        env_var="CAE_CONFIG_DIR",
        manifest_keys=("app", "config_dir"),
        default=repo.app_config_dir,
    )
    profile_config = context.path_value(
        env_var="CAE_PROFILE_CONFIG",
        manifest_keys=("profile_config",),
        default=repo.profile_config,
    )
    goaccess_build_dir = context.path_value(
        env_var=ENV_GOACCESS_BUILD_DIR,
        manifest_keys=("goaccess", "build_dir"),
        default=repo.goaccess_build_dir,
    )
    goaccess_source_dir = context.path_value(
        env_var=ENV_GOACCESS_SOURCE_DIR,
        manifest_keys=("goaccess", "source_dir"),
        default=repo.goaccess_source_dir,
    )

    if (
        goaccess_exe is None
        or app_exe is None
        or config_dir is None
        or profile_config is None
        or goaccess_build_dir is None
        or goaccess_source_dir is None
    ):
        raise ValueError("required paths must resolve to real files or directories")

    print(">>> Step 0: Preparing clean output folders...")
    clean_output_tree(logs_dir, {".log", ".jsonl", ".json"})
    clean_output_tree(reports_dir, {".html", ".json", ".csv"})
    clean_build_logs(build_logs_dir)

    cmake_cache = context.path_value(
        manifest_keys=("goaccess", "cmake_cache"),
        default=goaccess_build_dir / "CMakeCache.txt",
    )
    cmake_config = context.path_value(
        manifest_keys=("goaccess", "config_h"),
        default=goaccess_build_dir / "config.h",
    )
    if cmake_cache.is_file() and cmake_config.is_file():
        print(">>> Step 1: Verifying autotools/CMake config parity...")
        parity_cmd = [
            sys.executable,
            "-m",
            "tools.verify.verify_goaccess_parity",
            "--generate-reference",
            "--source-dir",
            str(goaccess_source_dir),
            "--cmake-config",
            str(cmake_config),
            "--cmake-cache",
            str(cmake_cache),
            "--reference-build-dir",
            str(repo.build_dir / "goaccess_autotools_ref"),
            "--clean-reference-dir",
            "--report-file",
            str(parity_report),
        ]
        if cygwin_bash:
            parity_cmd.extend(["--cygwin-bash", cygwin_bash])
        run_checked(parity_cmd)

    print(">>> Step 2: Running 3 concurrent CAE demo processes...")
    return_code = run_demo_processes(
        app_exe=Path(app_exe),
        cwd=Path(config_dir),
        process_count=3,
        session_prefix="Proc",
        launcher=launch_demo_quietly,
    )
    if return_code != 0:
        sys.exit(return_code)

    print(">>> Step 3: Merging CAE JSONL logs...")
    merge_cae_logs(input_dir=build_logs_dir, output_log=json_log)

    verify_cae_pipeline(
        log_file=json_log,
        goaccess_exe=Path(goaccess_exe),
        profile_config=Path(profile_config),
        reports_dir=reports_dir,
        repo_root=repo.repo_root,
        run_probes=not args.skip_probes,
        minimum_lines=args.minimum_lines,
        report_prefix="e2e_report",
    )


if __name__ == "__main__":
    main()
