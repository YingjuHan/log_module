#!/usr/bin/env python3
"""Validate cae_logger_config.ini and document reload-safe keys."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BOOL_KEYS = {
    "truncate_file",
    "enable_console",
    "console",
    "enable_text_log",
    "text_log",
    "enable_analysis_log",
    "analysis_log",
    "enable_call_chain_analysis",
    "call_chain_analysis",
    "enable_stacktrace",
    "enable_lossy_drop_policy",
    "lossy_drop_policy",
    "flush_each_record",
    "immediate_flush",
    "write_through_files",
}

SIZE_KEYS = {
    "async_queue_size",
    "async_thread_count",
    "analysis_log_max_bytes",
    "analysis_log_retention_files",
    "logger_health_interval_events",
    "call_chain_max_depth",
    "stacktrace_depth",
    "call_chain_skip",
    "stacktrace_skip",
}

STRING_KEYS = {
    "global_pattern",
    "log_dir",
    "analysis_log_name",
    "job_id",
}

LEVEL_KEYS = {
    "min_level",
    "flush_level",
    "call_chain_min_level",
    "stacktrace_min_level",
    "lossy_drop_below_level",
    "drop_below_level",
}

FLOAT_KEYS = {
    "call_chain_sample_rate",
    "stacktrace_sample_rate",
}

MODEL_KEYS = {
    "thread_model",
    "process_model",
    "io_mode",
    "async_overflow_policy",
}

ALLOWED_KEYS = BOOL_KEYS | SIZE_KEYS | STRING_KEYS | LEVEL_KEYS | FLOAT_KEYS | MODEL_KEYS

HOT_RELOAD_KEYS = {
    "min_level",
    "flush_level",
    "global_pattern",
    "enable_call_chain_analysis",
    "call_chain_analysis",
    "enable_stacktrace",
    "call_chain_min_level",
    "stacktrace_min_level",
    "call_chain_max_depth",
    "stacktrace_depth",
    "call_chain_skip",
    "stacktrace_skip",
    "call_chain_sample_rate",
    "stacktrace_sample_rate",
    "enable_lossy_drop_policy",
    "lossy_drop_policy",
    "lossy_drop_below_level",
    "drop_below_level",
    "analysis_log_max_bytes",
    "analysis_log_retention_files",
    "logger_health_interval_events",
    "job_id",
    "flush_each_record",
    "immediate_flush",
    "write_through_files",
}

STARTUP_ONLY_KEYS = ALLOWED_KEYS - HOT_RELOAD_KEYS

BOOL_VALUES = {"true", "false", "1", "0", "yes", "no", "on", "off"}
LEVEL_VALUES = {"trace", "debug", "info", "warn", "warning", "error", "err", "critical", "fatal"}
THREAD_MODEL_VALUES = {"st", "singlethread", "single_thread", "mt", "multithread", "multi_thread"}
PROCESS_MODEL_VALUES = {"sp", "singleprocess", "single_process", "mp", "multiprocess", "multi_process"}
IO_MODE_VALUES = {"sync", "synchronous", "async", "asynchronous"}
ASYNC_OVERFLOW_VALUES = {"block", "blocking", "overrun_oldest", "overrunoldest", "drop_oldest"}


def _strip_comment(line: str) -> str:
    in_quote = False
    output: list[str] = []
    for char in line:
        if char == '"':
            in_quote = not in_quote
        if not in_quote and char in "#;":
            break
        output.append(char)
    return "".join(output).strip()


def parse_config(path: Path | str) -> tuple[dict[str, str], list[str]]:
    """Parse simple key=value config lines."""
    config_path = Path(path)
    values: dict[str, str] = {}
    errors: list[str] = []
    with config_path.open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            stripped = _strip_comment(raw)
            if not stripped:
                continue
            if "=" not in stripped:
                errors.append(f"{config_path}:{line_no}: expected key=value")
                continue
            key, value = stripped.split("=", 1)
            normalized_key = key.strip().lower()
            if not normalized_key:
                errors.append(f"{config_path}:{line_no}: empty key")
                continue
            values[normalized_key] = value.strip().strip('"')
    return values, errors


def _validate_size(key: str, value: str) -> str | None:
    try:
        parsed = int(value)
    except ValueError:
        return f"{key} must be a non-negative integer"
    if parsed < 0:
        return f"{key} must be non-negative"
    if key in {"async_queue_size", "async_thread_count"} and parsed == 0:
        return f"{key} must be greater than zero"
    return None


def _validate_float(key: str, value: str) -> str | None:
    try:
        parsed = float(value)
    except ValueError:
        return f"{key} must be a number"
    if key in {"call_chain_sample_rate", "stacktrace_sample_rate"} and not (0.0 <= parsed <= 1.0):
        return f"{key} must be between 0.0 and 1.0"
    return None


def validate_config_values(values: dict[str, str]) -> list[str]:
    """Validate parsed cae_logger config values."""
    errors: list[str] = []
    for key, value in values.items():
        lowered_value = value.strip().lower()
        if key not in ALLOWED_KEYS:
            errors.append(f"unknown key: {key}")
            continue
        if key in BOOL_KEYS and lowered_value not in BOOL_VALUES:
            errors.append(f"{key} must be a boolean")
        elif key in SIZE_KEYS:
            if error := _validate_size(key, lowered_value):
                errors.append(error)
        elif key in FLOAT_KEYS:
            if error := _validate_float(key, lowered_value):
                errors.append(error)
        elif key in LEVEL_KEYS and lowered_value not in LEVEL_VALUES:
            errors.append(f"{key} must be a known log level")
        elif key == "thread_model" and lowered_value not in THREAD_MODEL_VALUES:
            errors.append("thread_model must be SingleThread/ST or MultiThread/MT")
        elif key == "process_model" and lowered_value not in PROCESS_MODEL_VALUES:
            errors.append("process_model must be SingleProcess/SP or MultiProcess/MP")
        elif key == "io_mode" and lowered_value not in IO_MODE_VALUES:
            errors.append("io_mode must be Sync or Async")
        elif key == "async_overflow_policy" and lowered_value not in ASYNC_OVERFLOW_VALUES:
            errors.append("async_overflow_policy must be block or overrun_oldest")
    return errors


def validate_config(path: Path | str) -> dict[str, object]:
    """Validate a config file and return a structured report."""
    config_path = Path(path)
    values, errors = parse_config(config_path)
    errors.extend(validate_config_values(values))
    return {
        "config_file": str(config_path.resolve(strict=False)),
        "valid": not errors,
        "errors": errors,
        "key_count": len(values),
        "hot_reload_keys": sorted(key for key in values if key in HOT_RELOAD_KEYS),
        "startup_only_keys": sorted(key for key in values if key in STARTUP_ONLY_KEYS),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate cae_logger_config.ini")
    default_config = Path(__file__).resolve().parents[3] / "cae_log_module" / "config" / "cae_logger_config.ini"
    parser.add_argument("config", nargs="?", default=str(default_config))
    parser.add_argument("--json", action="store_true", help="Print a JSON report")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = validate_config(args.config)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["valid"]:
        print(f"Validated CAE logger config: {report['config_file']}")
    else:
        for error in report["errors"]:
            print(error, file=sys.stderr)
    if not report["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
