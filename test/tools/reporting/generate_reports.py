#!/usr/bin/env python3
"""Generate GoAccess HTML reports for merged CAE logs."""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tools.common.cae_env import (
    ENV_GOACCESS_EXE,
    ENV_PROFILE_CONFIG,
    RepoPaths,
    CaeContext,
    check_file,
    resolve_path,
)


EN_REPORT_TITLE = "CAE Log Statistics"
ZH_REPORT_TITLE = "CAE 日志统计"


@dataclass(frozen=True)
class ReportInputs:
    """All inputs required to generate GoAccess reports."""

    goaccess_exe: Path
    profile_config: Path
    log_file: Path
    report_dir: Path
    prefix: str
    locale_dir: Path | None
    skip_locale_copy: bool
    repo_paths: RepoPaths


def pick_log_file(context: CaeContext, cli_value: str | None) -> Path:
    """Resolve the input log path from CLI, manifest, or defaults."""
    if cli_value not in (None, ""):
        resolved = resolve_path(cli_value, context.repo_paths.repo_root)
        if resolved is None:
            raise ValueError("log_file must resolve to a file path")
        return resolved
    manifest_value = context.pick(manifest_keys=("log_file",), default=None)
    if manifest_value not in (None, ""):
        resolved = resolve_path(manifest_value, context.repo_paths.repo_root)
        if resolved is None:
            raise ValueError("manifest log_file must resolve to a file path")
        return resolved
    return (context.repo_paths.logs_dir / "cae_events.jsonl").resolve(strict=False)


def pick_path(
    context: CaeContext,
    *,
    cli_value: str | None,
    manifest_keys: tuple[str, ...],
    default: Path,
) -> Path:
    """Resolve a path using CLI > environment/manifest > default precedence."""
    chosen = context.pick(cli_value=cli_value, manifest_keys=manifest_keys, default=default)
    resolved = resolve_path(chosen, context.repo_paths.repo_root)
    if resolved is None:
        raise ValueError(f"Failed to resolve path for {manifest_keys or ('cli',)}")
    return resolved


def normalize_report_title(output_file: Path, report_title: str) -> None:
    """Normalize the generated HTML title and header text."""
    escaped_title_bytes = html.escape(report_title).encode("utf-8")
    html_bytes = output_file.read_bytes()
    html_bytes, title_replacements = re.subn(
        rb"<title>.*?</title>",
        b"<title>" + escaped_title_bytes + b"</title>",
        html_bytes,
        count=1,
        flags=re.DOTALL,
    )
    html_bytes, header_replacements = re.subn(
        rb"(<p class='report-title' id='report-title'>).*?(</p>)",
        rb"\1" + escaped_title_bytes + rb"\2",
        html_bytes,
        count=1,
        flags=re.DOTALL,
    )
    if title_replacements != 1 or header_replacements != 1:
        raise RuntimeError(f"Failed to normalize report title in {output_file}")
    output_file.write_bytes(html_bytes)


def copy_runtime_locale(locale_dir: Path, repo: RepoPaths) -> Path | None:
    """Copy GoAccess zh_CN locale data next to the runtime executable when available."""
    zh_runtime_mo = locale_dir / "zh_CN" / "LC_MESSAGES" / "goaccess.mo"
    for source_mo in (
        repo.goaccess_source_dir / "po" / "zh_CN.mo",
        repo.goaccess_source_dir / "po" / "zh_CN.gmo",
    ):
        if source_mo.is_file():
            zh_runtime_mo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_mo, zh_runtime_mo)
            return zh_runtime_mo
    return None


def run_goaccess(
    *,
    goaccess: Path,
    profile: Path,
    logfile: Path,
    output_file: Path,
    report_title: str,
    lang: str,
    language_env: str | None,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> None:
    """Run GoAccess and verify that the expected HTML file is produced."""
    env = dict(os.environ)
    env["LANG"] = lang
    env["LC_ALL"] = lang
    if language_env:
        env["LANGUAGE"] = language_env
    else:
        env.pop("LANGUAGE", None)

    result = runner(
        [
            str(goaccess),
            "-f",
            str(logfile),
            "-p",
            str(profile),
            "-o",
            str(output_file),
            "--html-report-title",
            report_title,
            "--no-global-config",
        ],
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"GoAccess execution failed (exit code {result.returncode}): {goaccess}")
    if not output_file.is_file():
        raise RuntimeError(f"Expected report was not created: {output_file}")
    normalize_report_title(output_file, report_title)


def resolve_report_inputs(args: argparse.Namespace, repo: RepoPaths | None = None) -> ReportInputs:
    """Resolve report inputs from CLI arguments and manifest defaults."""
    context = CaeContext.create(repo_paths=repo, manifest_path=args.manifest)
    goaccess_exe = context.path_value(
        cli_value=args.goaccess_exe,
        env_var=ENV_GOACCESS_EXE,
        manifest_keys=("goaccess", "exe"),
        default=context.repo_paths.goaccess_exe,
    )
    profile_config = context.path_value(
        cli_value=args.profile_config,
        env_var=ENV_PROFILE_CONFIG,
        manifest_keys=("profile_config",),
        default=context.repo_paths.profile_config,
    )
    report_dir = pick_path(
        context,
        cli_value=args.report_dir,
        manifest_keys=("reports_dir",),
        default=context.repo_paths.reports_dir,
    )
    if goaccess_exe is None or profile_config is None:
        raise ValueError("goaccess_exe and profile_config must resolve to paths")
    locale_dir = resolve_path(args.locale_dir, context.repo_paths.repo_root) if args.locale_dir else None
    return ReportInputs(
        goaccess_exe=goaccess_exe,
        profile_config=profile_config,
        log_file=pick_log_file(context, args.log_file),
        report_dir=report_dir,
        prefix=args.prefix,
        locale_dir=locale_dir,
        skip_locale_copy=args.skip_locale_copy,
        repo_paths=context.repo_paths,
    )


def generate_reports(
    inputs: ReportInputs,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> tuple[Path, Path]:
    """Generate English and Chinese GoAccess reports."""
    goaccess = check_file(inputs.goaccess_exe, "GoAccess executable")
    profile = check_file(inputs.profile_config, "CAE profile")
    logfile = check_file(inputs.log_file, "Log file")
    if logfile.stat().st_size == 0:
        raise ValueError(f"Log file is empty: {logfile}")

    report_dir = inputs.report_dir.resolve(strict=False)
    report_dir.mkdir(parents=True, exist_ok=True)
    if not inputs.skip_locale_copy:
        copy_runtime_locale(inputs.locale_dir or (goaccess.parent / "locale"), inputs.repo_paths)

    en_report = report_dir / f"{inputs.prefix}_en.html"
    zh_report = report_dir / f"{inputs.prefix}_zh.html"
    run_goaccess(
        goaccess=goaccess,
        profile=profile,
        logfile=logfile,
        output_file=en_report,
        report_title=EN_REPORT_TITLE,
        lang="en_US.UTF-8",
        language_env=None,
        runner=runner,
    )
    run_goaccess(
        goaccess=goaccess,
        profile=profile,
        logfile=logfile,
        output_file=zh_report,
        report_title=ZH_REPORT_TITLE,
        lang="zh_CN.UTF-8",
        language_env="zh_CN",
        runner=runner,
    )
    return en_report, zh_report


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    repo = RepoPaths.discover(__file__)
    parser = argparse.ArgumentParser(description="Generate GoAccess CAE HTML reports")
    parser.add_argument("--manifest", default=str(repo.manifest_path))
    parser.add_argument("--log-file", default=None)
    parser.add_argument("--report-dir", default=None)
    parser.add_argument("--prefix", default="report")
    parser.add_argument("--profile-config", default=None)
    parser.add_argument("--goaccess-exe", default=None)
    parser.add_argument("--locale-dir", default=None)
    parser.add_argument("--skip-locale-copy", action="store_true")
    return parser


def main() -> None:
    """CLI entry point."""
    args = build_parser().parse_args()
    try:
        reports = generate_reports(resolve_report_inputs(args))
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        sys.exit(str(exc))
    print(f"Wrote {reports[0]}")
    print(f"Wrote {reports[1]}")


if __name__ == "__main__":
    main()
