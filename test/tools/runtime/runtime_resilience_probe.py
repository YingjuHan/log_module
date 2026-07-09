#!/usr/bin/env python3
"""Run a small CAE logger resilience smoke test with tiny rotation thresholds."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tools.common.cae_env import CaeContext, ENV_APP_EXE, ENV_CONFIG_DIR, check_dir, check_file
from tools.pipeline.export_cae_events import export_cae_events
from tools.pipeline.merge_cae_logs import merge_cae_logs
from tools.pipeline.cae_event_view import load_validated_events
from tools.pipeline.validate_cae_events import collect_jsonl_stats
from tools.reporting.summarize_cae_report import write_summary_artifacts
from tools.runtime.run_demo import run_demo_processes


def upsert_config_key(text: str, key: str, value: str) -> str:
    """Replace a simple key=value line or append it when absent."""
    replacement = f"{key} = {value}"
    lines = text.splitlines()
    replaced = False
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        line_key = stripped.split("=", 1)[0].strip().lower() if "=" in stripped else ""
        if stripped and not stripped.startswith(("#", ";")) and line_key == key.lower():
            output.append(replacement)
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(replacement)
    return "\n".join(output) + "\n"


def write_resilience_config(
    source_config: Path,
    target_dir: Path,
    *,
    max_bytes: int,
    health_interval: int,
    retention_files: int,
) -> Path:
    """Copy a config into a run directory and force resilience knobs to tiny values."""
    text = source_config.read_text(encoding="utf-8")
    overrides = {
        "process_model": "MP",
        "io_mode": "Async",
        "enable_console": "false",
        "analysis_log_max_bytes": str(max_bytes),
        "analysis_log_retention_files": str(retention_files),
        "logger_health_interval_events": str(health_interval),
    }
    for key, value in overrides.items():
        text = upsert_config_key(text, key, value)

    target_dir.mkdir(parents=True, exist_ok=True)
    target_config = target_dir / source_config.name
    target_config.write_text(text, encoding="utf-8")
    return target_config


def quiet_launcher(args: list[str], cwd: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(args, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def count_logger_health_events(path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            if not raw.strip():
                continue
            item = json.loads(raw)
            if item.get("component") == "Logger" and item.get("action") == "health_snapshot":
                count += 1
    return count


def assert_resilience_artifacts(logs_dir: Path, reports_dir: Path, merged_log: Path, *, prefix: str) -> None:
    rotated_logs = sorted(logs_dir.glob("cae_events*_*.jsonl"))
    if not rotated_logs:
        raise RuntimeError(f"No rotated CAE JSONL segments found in {logs_dir}")
    if count_logger_health_events(merged_log) < 1:
        raise RuntimeError(f"No Logger health_snapshot events found in {merged_log}")

    summary_path = reports_dir / "cae_summary.json"
    if not summary_path.is_file():
        raise RuntimeError(f"Missing summary artifact: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    logger_health = summary.get("logger_health")
    if not isinstance(logger_health, dict) or logger_health.get("health_event_count", 0) < 1:
        raise RuntimeError("Summary logger_health section did not record health snapshots")
    if logger_health.get("segments_created", 0) < 1:
        raise RuntimeError("Summary logger_health section did not record segment creation")

    export_csv = reports_dir / f"{prefix}.csv"
    if not export_csv.is_file() or export_csv.stat().st_size == 0:
        raise RuntimeError(f"Missing export CSV artifact: {export_csv}")


def run_resilience_probe(
    *,
    app_exe: Path,
    source_config_dir: Path,
    alert_config: Path,
    work_dir: Path,
    max_bytes: int,
    health_interval: int,
    retention_files: int,
    require_columnar: bool,
) -> dict[str, Path]:
    app = check_file(app_exe, "Demo executable")
    config_dir = check_dir(source_config_dir, "Demo config directory")
    source_config = check_file(config_dir / "cae_logger_config.ini", "CAE logger config")

    run_dir = work_dir / "run"
    logs_dir = run_dir / "logs"
    reports_dir = work_dir / "reports"
    merged_dir = work_dir / "merged"
    for path in (run_dir, reports_dir, merged_dir):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)

    write_resilience_config(
        source_config,
        run_dir,
        max_bytes=max_bytes,
        health_interval=health_interval,
        retention_files=retention_files,
    )

    return_code = run_demo_processes(
        app_exe=app,
        cwd=run_dir,
        process_count=1,
        session_prefix="Resilience",
        launcher=quiet_launcher,
    )
    if return_code != 0:
        raise RuntimeError(f"Resilience demo failed with exit code {return_code}")

    merged_log = merged_dir / "cae_events.jsonl"
    merge_cae_logs(input_dir=logs_dir, output_log=merged_log)
    _, invalid_rows = collect_jsonl_stats(str(merged_log), require_schema_version="cae_event_v1")
    if invalid_rows:
        raise RuntimeError(f"Resilience merged log has {len(invalid_rows)} invalid row(s)")

    events = load_validated_events(str(merged_log))
    write_summary_artifacts(
        input_path=merged_log,
        output_dir=reports_dir,
        alert_config_path=alert_config,
        events=events,
    )
    export_cae_events(
        merged_log,
        reports_dir,
        prefix="cae_events",
        require_columnar=require_columnar,
        observability=True,
    )
    assert_resilience_artifacts(logs_dir, reports_dir, merged_log, prefix="cae_events")

    return {
        "work_dir": work_dir,
        "logs_dir": logs_dir,
        "merged_log": merged_log,
        "reports_dir": reports_dir,
    }


def build_parser() -> argparse.ArgumentParser:
    context = CaeContext.create(repo_paths=None)
    parser = argparse.ArgumentParser(description="Run a CAE logger runtime resilience smoke probe")
    parser.add_argument("--manifest", default=str(context.manifest_path), help="Optional manifest JSON")
    parser.add_argument("--app-exe", default=None, help="Demo executable path")
    parser.add_argument("--config-dir", default=None, help="Source config directory containing cae_logger_config.ini")
    parser.add_argument("--work-dir", default=None, help="Optional work directory to preserve probe artifacts")
    parser.add_argument("--max-bytes", type=int, default=4096, help="Tiny analysis log rotation threshold")
    parser.add_argument("--health-interval", type=int, default=20, help="Application events between health snapshots")
    parser.add_argument("--retention-files", type=int, default=0, help="Rotated segment retention cap; 0 means unlimited")
    parser.add_argument("--require-columnar", action="store_true", help="Require pyarrow Arrow/Parquet export")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        context = CaeContext.create(manifest_path=args.manifest)
        app_exe = context.path_value(
            cli_value=args.app_exe,
            env_var=ENV_APP_EXE,
            manifest_keys=("app", "exe"),
            default=context.repo_paths.app_exe,
        )
        source_config_dir = context.path_value(
            cli_value=args.config_dir,
            env_var=ENV_CONFIG_DIR,
            manifest_keys=("app", "config_dir"),
            default=context.repo_paths.app_config_dir,
        )
        if app_exe is None or source_config_dir is None:
            raise ValueError("app_exe and config_dir must resolve to real paths")

        if args.work_dir:
            work_dir = Path(args.work_dir).expanduser().resolve(strict=False)
            work_dir.mkdir(parents=True, exist_ok=True)
            result = run_resilience_probe(
                app_exe=Path(app_exe),
                source_config_dir=Path(source_config_dir),
                alert_config=context.repo_paths.config_dir / "cae_alerts.json",
                work_dir=work_dir,
                max_bytes=args.max_bytes,
                health_interval=args.health_interval,
                retention_files=args.retention_files,
                require_columnar=args.require_columnar,
            )
        else:
            with tempfile.TemporaryDirectory(prefix="cae_resilience_probe_") as temp_dir_name:
                result = run_resilience_probe(
                    app_exe=Path(app_exe),
                    source_config_dir=Path(source_config_dir),
                    alert_config=context.repo_paths.config_dir / "cae_alerts.json",
                    work_dir=Path(temp_dir_name),
                    max_bytes=args.max_bytes,
                    health_interval=args.health_interval,
                    retention_files=args.retention_files,
                    require_columnar=args.require_columnar,
                )
                print(f"Resilience probe passed in temporary work dir: {result['work_dir']}")
                return
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        sys.exit(str(exc))

    print(f"Resilience probe passed: {result['work_dir']}")
    print(f"Logs: {result['logs_dir']}")
    print(f"Merged log: {result['merged_log']}")
    print(f"Reports: {result['reports_dir']}")


if __name__ == "__main__":
    main()
