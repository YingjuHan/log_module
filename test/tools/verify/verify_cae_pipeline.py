#!/usr/bin/env python3
"""Validate a CAE JSONL log pipeline without rebuilding artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.common.cae_env import (
    CaeContext,
    ENV_GOACCESS_EXE,
    ENV_LOGS_DIR,
    ENV_PROFILE_CONFIG,
    ENV_REPORTS_DIR,
    RepoPaths,
    resolve_path,
    run_checked,
)
from tools.pipeline.cae_event_view import filter_events, load_validated_events
from tools.pipeline.validate_cae_events import collect_jsonl_stats, load_jsonl_stats
from tools.reporting.generate_reports import ReportInputs, generate_reports
from tools.reporting.summarize_cae_report import write_summary_artifacts
from tools.runtime.cleanup_cae_logs import collect_candidates, select_deletions


TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SPAN_ID_RE = re.compile(r"^[0-9a-f]{16}$")
CAE_PANEL_KEYS = [
    "cae_events",
    "cae_module_dist",
    "cae_severity",
    "cae_duration",
    "cae_session",
    "cae_timeline",
]
CAE_REPORT_MARKERS = [
    "Events Overview",
    "Module Distribution",
    "Severity Breakdown",
    "Duration Analysis",
    "Session Overview",
    "Event Timeline",
]


def resolve_log_file(context: CaeContext, cli_value: str | None) -> Path:
    """Resolve the merged log file using CLI, manifest, or default logs directory."""
    if cli_value not in (None, ""):
        resolved = resolve_path(cli_value, context.repo_paths.repo_root)
        if resolved is None:
            raise ValueError("log_file must resolve to a file path")
        return resolved

    manifest_log_file = context.pick(manifest_keys=("log_file",), default=None)
    if manifest_log_file not in (None, ""):
        resolved = resolve_path(manifest_log_file, context.repo_paths.repo_root)
        if resolved is None:
            raise ValueError("manifest log_file must resolve to a file path")
        return resolved

    logs_root = context.path_value(
        env_var=ENV_LOGS_DIR,
        manifest_keys=("logs_dir",),
        default=context.repo_paths.logs_dir,
    )
    if logs_root is None:
        raise ValueError("logs_dir must resolve to a directory")
    return logs_root / "cae_events.jsonl"


def check(cmd: list[str], cwd: Path | None = None, timeout: int = 300) -> None:
    """Run a command and exit with the command error on failure."""
    try:
        run_checked(cmd, cwd=cwd, timeout=timeout)
    except RuntimeError as exc:
        sys.exit(str(exc))


def expect_report_title(html_text: str, expected_title: str, report_path: Path) -> None:
    """Verify both HTML title locations."""
    title_match = re.search(r"<title>(.*?)</title>", html_text, flags=re.DOTALL)
    if not title_match:
        sys.exit(f"Missing <title> element in {report_path}")
    head_title = title_match.group(1).replace("&nbsp;", " ").strip()
    if head_title != expected_title:
        sys.exit(f"Expected HTML <title> '{expected_title}' in {report_path}, got '{head_title}'")

    header_match = re.search(
        r"<p class='report-title' id='report-title'>(.*?)</p>",
        html_text,
        flags=re.DOTALL,
    )
    if not header_match:
        sys.exit(f"Missing report header title in {report_path}")
    header_title = header_match.group(1).replace("&nbsp;", " ").strip()
    if header_title != expected_title:
        sys.exit(
            f"Expected report header title '{expected_title}' in {report_path}, got '{header_title}'"
        )


def expect_report_markers(html_text: str, markers: list[str], report_path: Path) -> None:
    """Verify all expected semantic report markers are present."""
    missing = [marker for marker in markers if marker not in html_text]
    if missing:
        sys.exit(f"Missing report markers in {report_path}: {', '.join(missing)}")


def read_report_text(report_path: Path) -> str:
    """Read generated HTML reports while tolerating non-UTF-8 bytes from GoAccess."""
    return report_path.read_text(encoding="utf-8", errors="replace")


def load_goaccess_json(json_path: Path) -> dict[str, object]:
    """Load GoAccess JSON while tolerating non-UTF-8 bytes in string values."""
    payload = json_path.read_text(encoding="utf-8", errors="replace")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        sys.exit(f"GoAccess JSON root must be an object: {json_path}")
    return parsed


def expect_equal(label: str, actual: object, expected: object) -> None:
    """Exit if two values differ."""
    if actual != expected:
        sys.exit(f"{label} mismatch: expected {expected}, got {actual}")


def require_panel_data(parsed: dict[str, object], panel_key: str) -> dict[str, object]:
    """Return a non-empty GoAccess panel payload."""
    panel = parsed.get(panel_key)
    if not isinstance(panel, dict):
        sys.exit(f"JSON output missing '{panel_key}' panel object")
    data = panel.get("data")
    if not isinstance(data, list) or not data:
        sys.exit(f"JSON output panel '{panel_key}' has no data rows")
    return panel


def get_panel_unique_total(panel: dict[str, object], panel_key: str) -> object:
    """Read a GoAccess panel unique count."""
    try:
        metadata = panel["metadata"]
        if not isinstance(metadata, dict):
            raise KeyError("metadata")
        metadata_data = metadata["data"]
        if not isinstance(metadata_data, dict):
            raise KeyError("data")
        total = metadata_data["total"]
        if not isinstance(total, dict):
            raise KeyError("total")
        return total["value"]
    except KeyError as exc:
        sys.exit(f"JSON output panel '{panel_key}' missing metadata.data.total.value: {exc}")


def validate_duration_panel(panel: dict[str, object], stats: dict[str, object]) -> None:
    """Compare GoAccess duration panel rows with JSONL stats."""
    rows = {
        row.get("data"): row
        for row in panel.get("data", [])
        if isinstance(row, dict)
    }
    durations_by_module = stats["durations_by_module"]
    if not isinstance(durations_by_module, dict):
        sys.exit("durations_by_module is not available in JSONL stats")

    for module, expected in durations_by_module.items():
        row = rows.get(module)
        if not isinstance(row, dict):
            sys.exit(f"cae_duration missing module row: {module}")
        count = row.get("count")
        if not isinstance(count, dict):
            sys.exit(f"cae_duration row missing count payload for module: {module}")
        expect_equal(f"cae_duration {module} count", count.get("count"), expected["count"])
        expect_equal(f"cae_duration {module} cumts", row.get("cumts"), expected["sum"])
        expect_equal(f"cae_duration {module} maxts", row.get("maxts"), expected["max"])
        expect_equal(f"cae_duration {module} avgts", row.get("avgts"), expected["sum"] // expected["count"])


def validate_cae_json_output(
    parsed: dict[str, object],
    stats: dict[str, object],
    source_path: Path,
) -> None:
    """Validate GoAccess JSON output against JSONL semantic stats."""
    general = parsed.get("general")
    if not isinstance(general, dict):
        sys.exit("JSON output missing 'general' panel data")

    line_count = stats["line_count"]
    module_count = len(stats["modules"])
    session_count = len(stats["sessions"])

    expect_equal("general.total_requests", general.get("total_requests"), line_count)
    expect_equal("general.total_events", general.get("total_events"), line_count)
    expect_equal("general.total_modules", general.get("total_modules"), module_count)
    expect_equal("general.total_sessions", general.get("total_sessions"), session_count)

    for panel_key in CAE_PANEL_KEYS:
        panel = require_panel_data(parsed, panel_key)
        if panel_key == "cae_module_dist":
            expect_equal(
                "cae_module_dist metadata unique count",
                get_panel_unique_total(panel, panel_key),
                module_count,
            )
        if panel_key == "cae_session":
            expect_equal(
                "cae_session metadata unique count",
                get_panel_unique_total(panel, panel_key),
                session_count,
            )
        if panel_key == "cae_duration":
            validate_duration_panel(panel, stats)

    print(
        f">>> CAE semantic check passed for {source_path}: "
        f"{line_count} events, {module_count} modules, {session_count} sessions"
    )


def make_probe_row(
    idx: int,
    component: str,
    stage: str,
    action: str,
    level: str,
    event_kind: str,
    duration_us: int,
    message: str,
    *,
    metrics: dict[str, object] | None = None,
    result: str | None = None,
    reason: str | None = None,
    parent_span_id: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    node_id: str = "probe-node",
    mpi_rank: int = 0,
) -> dict[str, object]:
    """Create one schema v1 probe row."""
    trace_value = trace_id or f"{idx:032x}"[-32:]
    span_value = span_id or f"{idx:016x}"[-16:]
    return {
        "schema_version": "cae_event_v1",
        "timestamp": f"2026-06-08T10:00:{idx:02d}.000",
        "timestamp_epoch_us": 1780893600000000 + idx * 1_000_000,
        "monotonic_us": idx * 1_000_000,
        "date": "2026-06-08",
        "time": f"10:00:{idx:02d}",
        "source": f"pid:probe/tid:{idx}",
        "component": component,
        "stage": stage,
        "action": action,
        "level": level,
        "message": message,
        "event_kind": event_kind,
        "event_type": "system",
        "phase": "end" if event_kind == "span" else "progress",
        "domain": "system",
        "entity_type": stage,
        "entity_name": action,
        "duration_us": duration_us,
        "size": len(message.encode("utf-8")),
        "session": f"Probe_{1 + (idx % 2)}",
        "job_id": "ProbeJob",
        "thread_name": f"probe-thread-{idx}",
        "sequence": idx,
        "global_sequence_id": f"ProbeJob:probe-node:{mpi_rank}:{idx}",
        "logical_time": idx,
        "trace_id": trace_value,
        "span_id": span_value,
        "event_id": span_value,
        "parent_span_id": parent_span_id,
        "parent_event_id": parent_span_id,
        "object_type": None,
        "object_name": None,
        "result": result,
        "reason": reason,
        "node_id": node_id,
        "mpi_rank": mpi_rank,
        "metrics": metrics or {},
    }


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write probe rows to JSONL."""
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_malicious_probe_log(path: Path) -> dict[str, object]:
    """Write parser/escaping edge-case rows."""
    payloads = [
        make_probe_row(1, "Probe.Security", "Security", "message", "INFO", "point", 0, "<script>alert(1)</script>"),
        make_probe_row(2, "Probe.Security", "Security", "message", "WARN", "point", 0, "${jndi:ldap://example.invalid/a}"),
        make_probe_row(3, "Probe.Parser", "Parser", "message", "INFO", "point", 0, 'Quoted "value" with slash \\ and newline \\n marker'),
        make_probe_row(4, "Probe.Parser", "Parser", "message", "ERROR", "span", 4000, "JSON braces { } brackets [ ] ampersand & less < greater >"),
        make_probe_row(5, "Probe.Long", "Long", "message", "INFO", "point", 0, "long-event-" + ("x" * 2048)),
        make_probe_row(6, "Probe.Duration", "Duration", "message", "CRITICAL", "span", 6000, "Critical probe with explicit duration_us"),
    ]
    write_jsonl(path, payloads)
    return load_jsonl_stats(str(path))


def fail_if_invalid_requests(path: Path, label: str) -> None:
    """Fail if GoAccess wrote invalid request rows."""
    if path.is_file() and path.stat().st_size > 0:
        sys.exit(f"GoAccess reported invalid {label} JSONL lines: {path}")


def write_invalid_schema_probe_log(path: Path) -> int:
    """Write intentionally invalid rows and return their count."""
    rows = [
        {**make_probe_row(1, "Bad.Component", "Bad", "message", "INFO", "point", 0, "missing component"), "component": ""},
        {**make_probe_row(2, "Bad.Duration", "Bad", "message", "INFO", "point", 2, "point with duration")},
        {**make_probe_row(3, "Bad.Duration", "Bad", "message", "INFO", "span", 0, "span without duration")},
        {**make_probe_row(4, "Bad.Session", "Bad", "message", "WARN", "point", 0, "missing event kind"), "event_kind": None},
        {**make_probe_row(5, "Bad.Trace", "Bad", "message", "INFO", "point", 0, "bad trace"), "trace_id": "xyz"},
        {**make_probe_row(6, "Bad.Metrics", "Bad", "message", "INFO", "point", 0, "bad metrics"), "metrics": []},
    ]
    write_jsonl(path, rows)
    return len(rows)


def expect_point_and_span_samples(path: Path) -> None:
    """Ensure the merged log contains representative point/span data."""
    point_found = False
    span_found = False
    span_memory_found = False
    node_id_found = False
    mpi_rank_found = False
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            if not raw.strip():
                continue
            item = json.loads(raw)
            if "event" in item:
                sys.exit(f"Legacy event field unexpectedly present in {path}")
            if not item.get("message"):
                sys.exit(f"Missing message field in {path}")
            if not TRACE_ID_RE.fullmatch(str(item.get("trace_id", ""))):
                sys.exit(f"Invalid trace_id format in {path}")
            if not SPAN_ID_RE.fullmatch(str(item.get("span_id", ""))):
                sys.exit(f"Invalid span_id format in {path}")
            if item.get("node_id"):
                node_id_found = True
            if item.get("mpi_rank") is not None:
                mpi_rank_found = True
            if item.get("event_kind") == "point" and item.get("duration_us") == 0:
                point_found = True
            if item.get("event_kind") == "span" and isinstance(item.get("duration_us"), int) and item["duration_us"] > 0:
                span_found = True
                metrics = item.get("metrics")
                if isinstance(metrics, dict) and isinstance(metrics.get("memory_mb"), (int, float)):
                    span_memory_found = True
            if point_found and span_found and span_memory_found and node_id_found and mpi_rank_found:
                return
    if not point_found:
        sys.exit(f"No point event sample with duration_us == 0 found in {path}")
    if not span_found:
        sys.exit(f"No span event sample with duration_us > 0 found in {path}")
    if not span_memory_found:
        sys.exit(f"No span event sample with metrics.memory_mb found in {path}")
    if not node_id_found:
        sys.exit(f"No node_id field found in {path}")
    if not mpi_rank_found:
        sys.exit(f"No mpi_rank field found in {path}")


def validate_trace_context(path: Path) -> None:
    """Validate basic trace/span parent consistency."""
    events: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            if raw.strip():
                events.append(json.loads(raw))

    traces_by_session: dict[str, set[str]] = {}
    span_rows: dict[str, dict[str, object]] = {}
    nested_scope_found = False
    point_with_parent_found = False

    for item in events:
        session = str(item["session"])
        trace_id = str(item["trace_id"])
        span_id = str(item["span_id"])
        traces_by_session.setdefault(session, set()).add(trace_id)
        span_rows[span_id] = item
        if item["event_kind"] == "point" and item.get("parent_span_id"):
            point_with_parent_found = True

    for session, trace_ids in traces_by_session.items():
        if len(trace_ids) != 1:
            sys.exit(f"Expected session {session} to use exactly one trace_id, got {len(trace_ids)}")

    for item in events:
        parent_span_id = item.get("parent_span_id")
        if not parent_span_id:
            continue
        parent = span_rows.get(str(parent_span_id))
        if not parent:
            continue
        if parent["trace_id"] != item["trace_id"]:
            sys.exit("Found parent_span_id that crosses trace boundaries")
        if item["event_kind"] == "span":
            nested_scope_found = True

    if not nested_scope_found:
        sys.exit(f"No nested span with parent_span_id found in {path}")
    if not point_with_parent_found:
        sys.exit(f"No point event with parent_span_id found in {path}")


def run_invalid_schema_probe(logs_dir: Path) -> None:
    """Verify invalid schema rows fail preflight validation."""
    print(">>> Step 9: Running invalid schema preflight probe...")
    invalid_log = logs_dir / "cae_invalid_schema_probe.jsonl"
    invalid_report = logs_dir / "cae_invalid_schema_preflight.log"
    expected_invalid = write_invalid_schema_probe_log(invalid_log)
    _, invalid_rows = collect_jsonl_stats(str(invalid_log), invalid_path=str(invalid_report))
    if not invalid_rows:
        sys.exit("Invalid schema probe unexpectedly passed validation")
    with invalid_report.open(encoding="utf-8") as fh:
        invalid_count = sum(1 for line in fh if line.strip())
    if invalid_count != expected_invalid:
        sys.exit(f"Invalid schema probe mismatch: expected {expected_invalid}, got {invalid_count}")


def run_semantic_profile_probe(
    goaccess_exe: Path,
    profile_config: Path,
    json_log: Path,
    logs_dir: Path,
) -> None:
    """Verify GoAccess rejects an unknown semantic profile."""
    print(">>> Step 10: Verifying semantic-profile rejects unknown profiles...")
    bad_profile = logs_dir / "cae_bad_semantic_profile.conf"
    bad_profile.write_text(
        profile_config.read_text(encoding="utf-8").replace("semantic-profile cae", "semantic-profile not_a_profile"),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            str(goaccess_exe),
            "-f",
            str(json_log),
            "-p",
            str(bad_profile),
            "--process-and-exit",
            "--no-global-config",
        ],
        timeout=300,
        check=False,
    )
    if result.returncode == 0:
        sys.exit("Unknown semantic-profile unexpectedly succeeded")


def run_malicious_log_probe(
    goaccess_exe: Path,
    profile_config: Path,
    logs_dir: Path,
    reports_dir: Path,
) -> None:
    """Run parser and HTML escaping probes."""
    print(">>> Step 8: Running malicious/edge JSONL probe...")
    probe_log = logs_dir / "cae_malicious_probe.jsonl"
    probe_invalid = logs_dir / "cae_malicious_invalid.log"
    probe_schema_invalid = logs_dir / "cae_malicious_schema_invalid.log"
    probe_json = logs_dir / "cae_malicious_probe.json"
    probe_html = reports_dir / "cae_malicious_probe.html"

    for path in (probe_invalid, probe_schema_invalid, probe_json, probe_html):
        if path.is_file():
            path.unlink()

    probe_stats = write_malicious_probe_log(probe_log)
    load_jsonl_stats(str(probe_log), invalid_path=str(probe_schema_invalid))
    check([
        str(goaccess_exe), "-f", str(probe_log), "-p", str(profile_config),
        "--process-and-exit", "--invalid-requests", str(probe_invalid), "--no-global-config",
    ])
    fail_if_invalid_requests(probe_invalid, "malicious probe")

    check([str(goaccess_exe), "-f", str(probe_log), "-p", str(profile_config), "-o", str(probe_json), "--no-global-config"])
    validate_cae_json_output(load_goaccess_json(probe_json), probe_stats, probe_log)

    check([
        str(goaccess_exe), "-f", str(probe_log), "-p", str(profile_config),
        "-o", str(probe_html), "--html-report-title", "CAE Malicious Probe", "--no-global-config",
    ])
    probe_html_text = read_report_text(probe_html)
    if "<script>alert(1)</script>" in probe_html_text:
        sys.exit(f"Unescaped script payload found in {probe_html}")
    expect_report_markers(probe_html_text, CAE_REPORT_MARKERS, probe_html)


def validate_summary_outputs(output_dir: Path, stats: dict[str, object], source_file: Path) -> None:
    """Validate summary JSON/CSV artifacts."""
    summary_path = output_dir / "cae_summary.json"
    module_csv_path = output_dir / "cae_module_stats.csv"
    alerts_path = output_dir / "cae_alerts.json"
    for path in (summary_path, module_csv_path, alerts_path):
        if not path.is_file():
            sys.exit(f"Missing summary artifact: {path}")
        if path.stat().st_size == 0:
            sys.exit(f"Summary artifact is empty: {path}")

    with summary_path.open(encoding="utf-8") as fh:
        summary = json.load(fh)
    with alerts_path.open(encoding="utf-8") as fh:
        alerts = json.load(fh)

    expect_equal("summary.source_file", summary.get("source_file"), str(source_file.resolve(strict=False)))
    expect_equal("summary.total_events", summary.get("total_events"), stats["line_count"])
    expect_equal("summary.span_events", summary.get("span_events"), stats["event_kind_counts"].get("span", 0))
    expect_equal("summary.module_count", summary.get("module_count"), len(stats["modules"]))
    expect_equal("summary.session_count", summary.get("session_count"), len(stats["sessions"]))
    expect_equal("summary.trace_count", summary.get("trace_count"), len(stats["traces"]))
    if summary.get("node_count", 0) < 1:
        sys.exit("Summary missing node_count")
    span_stats = summary.get("span_stats")
    if not isinstance(span_stats, dict) or not span_stats.get("global"):
        sys.exit("Summary missing global span_stats")
    if "alerts" not in alerts or not isinstance(alerts["alerts"], list):
        sys.exit("Alert artifact missing alerts list")

    print(f">>> Summary artifacts validated for {source_file}")


def write_summary_probe_log(path: Path) -> str:
    """Create a synthetic summary/tail probe log."""
    shared_trace = "feedfacefeedfacefeedfacefeedface"
    workflow_span = "1111111111111111"
    rows = [
        make_probe_row(1, "Solver", "Solver", "workflow_started", "INFO", "point", 0, "Solver workflow started for case CASE_SUMMARY.", trace_id=shared_trace, parent_span_id=workflow_span),
        make_probe_row(2, "Solver", "Iteration", "nonlinear_step", "INFO", "point", 0, "Nonlinear iteration 001/003 completed.", metrics={"residual": 0.5, "courant": 0.8}, trace_id=shared_trace, parent_span_id=workflow_span),
        make_probe_row(3, "Mesh", "Mesh", "mesh_summary", "INFO", "point", 0, "Mesh summary generated.", metrics={"nodes": 100, "cells": 200, "blocks": 3, "fields": 4}, trace_id=shared_trace, parent_span_id=workflow_span),
        make_probe_row(4, "Solver", "Solver", "workflow", "WARN", "span", 900000, "Solver workflow completed.", metrics={"residual": 0.4, "courant": 0.9}, trace_id=shared_trace, span_id=workflow_span),
        make_probe_row(5, "PostProcess.Output", "Output", "export", "ERROR", "span", 1200000, 'Export failed for "result_big.plt".', result="failed", reason="disk_full", trace_id=shared_trace, parent_span_id=workflow_span),
    ]
    write_jsonl(path, rows)
    return shared_trace


def run_summary_probe(repo_root: Path, logs_dir: Path) -> None:
    """Validate summary and tail helper behavior with synthetic rows."""
    print(">>> Step 11: Running summary/tail synthetic probe...")
    probe_log = logs_dir / "cae_summary_probe.jsonl"
    probe_out_dir = logs_dir / "summary_probe_reports"
    probe_enriched = logs_dir / "cae_summary_probe_enriched.jsonl"

    if probe_out_dir.is_dir():
        shutil.rmtree(probe_out_dir)
    probe_out_dir.mkdir(parents=True, exist_ok=True)
    shared_trace = write_summary_probe_log(probe_log)

    write_summary_artifacts(
        input_path=probe_log,
        output_dir=probe_out_dir,
        alert_config_path=repo_root / "config" / "cae_alerts.json",
        write_enriched_jsonl_path=probe_enriched,
    )

    with (probe_out_dir / "cae_summary.json").open(encoding="utf-8") as fh:
        summary = json.load(fh)
    with (probe_out_dir / "cae_alerts.json").open(encoding="utf-8") as fh:
        alerts = json.load(fh)

    if summary.get("derived_fields_used"):
        sys.exit("Summary probe expected native structured fields")
    if summary.get("metric_summary", {}).get("residual", {}).get("sample_count") != 2:
        sys.exit("Summary probe residual sample_count mismatch")
    if summary.get("metric_summary", {}).get("nodes", {}).get("max") != 100:
        sys.exit("Summary probe nodes metric extraction failed")
    top_reasons = {item["value"] for item in summary.get("top_reasons", [])}
    if "disk_full" not in top_reasons:
        sys.exit("Summary probe failed to derive reason=disk_full")
    alert_ids = {alert["rule_id"] for alert in alerts.get("alerts", [])}
    if "global.span_p95_us" not in alert_ids:
        sys.exit("Summary probe failed to trigger global.span_p95_us alert")
    if not ({"global.error_rate", "global.residual_last_gt", "global.residual_drop_ratio_lt"} & alert_ids):
        sys.exit("Summary probe expected an error-rate or residual alert")
    if not probe_enriched.is_file() or probe_enriched.stat().st_size == 0:
        sys.exit("Summary probe did not write enriched JSONL output")

    tail_items = filter_events(load_validated_events(str(probe_log)), trace_id=shared_trace)[-5:]
    if len(tail_items) != 5:
        sys.exit(f"Expected exactly five tail items for shared trace, got {len(tail_items)}")
    if any(item.get("trace_id") != shared_trace for item in tail_items):
        sys.exit("Tail probe trace filter returned mixed trace_ids")
    if not any(item.get("metrics", {}).get("nodes") == 100 for item in tail_items):
        sys.exit("Tail probe did not emit expected native metrics")


def run_cleanup_probe() -> None:
    """Validate cleanup dry-run selection behavior."""
    print(">>> Step 12: Running cleanup probe...")
    with tempfile.TemporaryDirectory(prefix="cae_cleanup_probe_") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        old_log = temp_dir / "old.log"
        new_json = temp_dir / "new.jsonl"
        old_log.write_text("legacy\n", encoding="utf-8")
        new_json.write_text("{}\n", encoding="utf-8")
        stale_time = datetime(2020, 1, 1).timestamp()
        os.utime(old_log, (stale_time, stale_time))

        files = collect_candidates(str(temp_dir))
        dry_run = select_deletions(files, older_than_days=30)
        if len(dry_run) != 1 or dry_run[0]["path"] != str(old_log):
            sys.exit("cleanup dry-run selected unexpected files")
        if not old_log.is_file():
            sys.exit("cleanup dry-run unexpectedly deleted a file")

        for item in dry_run:
            os.remove(str(item["path"]))
        if old_log.exists():
            sys.exit("cleanup apply did not delete the stale file")
        if not new_json.is_file():
            sys.exit("cleanup apply deleted the fresh file unexpectedly")


def verify_cae_pipeline(
    *,
    log_file: Path,
    goaccess_exe: Path,
    profile_config: Path,
    reports_dir: Path,
    repo_root: Path,
    run_probes: bool = False,
    minimum_lines: int = 0,
    report_prefix: str = "e2e_report",
) -> None:
    """Run CAE log validation/report verification against existing outputs."""
    source_log = log_file.resolve(strict=False)
    goaccess = goaccess_exe.resolve(strict=False)
    profile = profile_config.resolve(strict=False)
    reports_path = reports_dir.resolve(strict=False)
    logs_dir = source_log.parent
    repo_paths = RepoPaths.discover(__file__)
    invalid_log = logs_dir / "invalid_requests.log"
    schema_invalid_log = logs_dir / "schema_invalid_requests.log"
    json_output = logs_dir / "cae_semantic_check.json"

    if not source_log.is_file():
        sys.exit(f"CAE JSONL log file not found: {source_log}")
    if source_log.stat().st_size == 0:
        sys.exit(f"CAE JSONL log file is empty: {source_log}")
    if not goaccess.is_file():
        sys.exit(f"GoAccess executable not found: {goaccess}")
    if not profile.is_file():
        sys.exit(f"CAE GoAccess profile config not found: {profile}")
    reports_path.mkdir(parents=True, exist_ok=True)

    print(">>> Step 4: Validating merged JSONL integrity...")
    with source_log.open(encoding="utf-8") as fh:
        line_count = sum(1 for _ in fh)
    if minimum_lines > 0:
        print(f">>> Total lines in CAE JSONL log: {line_count} (Minimum expected: {minimum_lines})")
        if line_count < minimum_lines:
            sys.exit(f"Line count too low. Expected at least {minimum_lines}, got {line_count}")
    else:
        print(f">>> Total lines in CAE JSONL log: {line_count}")
    expect_point_and_span_samples(source_log)
    validate_trace_context(source_log)

    print(">>> Step 5: Validating GoAccess CAE parser profile...")
    stats = load_jsonl_stats(str(source_log), invalid_path=str(schema_invalid_log))
    check([
        str(goaccess), "-f", str(source_log), "-p", str(profile),
        "--process-and-exit", "--invalid-requests", str(invalid_log), "--no-global-config",
    ])
    fail_if_invalid_requests(invalid_log, "CAE")

    print(">>> Step 6: Generating bilingual CAE HTML reports...")
    generate_reports(
        ReportInputs(
            goaccess_exe=goaccess,
            profile_config=profile,
            log_file=source_log,
            report_dir=reports_path,
            prefix=report_prefix,
            locale_dir=None,
            skip_locale_copy=False,
            repo_paths=repo_paths,
        )
    )

    print(">>> Step 7: Validating report files and CAE panel semantics...")
    expected_reports = [
        reports_path / f"{report_prefix}_en.html",
        reports_path / f"{report_prefix}_zh.html",
    ]
    for report in expected_reports:
        if not report.is_file():
            sys.exit(f"Missing report: {report}")
        if report.stat().st_size < 50000:
            sys.exit(f"Report too small (likely incomplete): {report} ({report.stat().st_size} bytes)")

    english_html = read_report_text(expected_reports[0])
    expect_report_title(english_html, "CAE Log Statistics", expected_reports[0])
    expect_report_markers(english_html, CAE_REPORT_MARKERS, expected_reports[0])

    chinese_html = read_report_text(expected_reports[1])
    expect_report_title(chinese_html, "CAE 日志统计", expected_reports[1])

    print(">>> Validating CAE semantic fields via GoAccess JSON output...")
    check([str(goaccess), "-f", str(source_log), "-p", str(profile), "-o", str(json_output), "--no-global-config"])
    if not json_output.is_file() or json_output.stat().st_size == 0:
        sys.exit(f"GoAccess JSON output not generated: {json_output}")
    parsed = load_goaccess_json(json_output)
    validate_cae_json_output(parsed, stats, source_log)

    print(">>> Step 8: Generating summary artifacts...")
    write_summary_artifacts(
        input_path=source_log,
        output_dir=reports_path,
        alert_config_path=repo_root / "config" / "cae_alerts.json",
    )
    validate_summary_outputs(reports_path, stats, source_log)

    if run_probes:
        run_malicious_log_probe(goaccess, profile, logs_dir, reports_path)
        run_invalid_schema_probe(logs_dir)
        run_semantic_profile_probe(goaccess, profile, source_log, logs_dir)
        run_summary_probe(repo_root, logs_dir)
        run_cleanup_probe()

    print(">>> [SUCCESS] CAE pipeline verification passed.")


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    context = CaeContext.create(repo_paths=None)
    parser = argparse.ArgumentParser(description="Verify an existing CAE log pipeline")
    parser.add_argument("--manifest", default=str(context.manifest_path), help="Optional manifest JSON")
    parser.add_argument("--log-file", default=None, help="Merged CAE JSONL log file")
    parser.add_argument("--goaccess-exe", default=None, help="GoAccess executable path")
    parser.add_argument("--profile-config", default=None, help="CAE GoAccess profile config")
    parser.add_argument("--reports-dir", default=None, help="Report output directory")
    parser.add_argument("--run-probes", action="store_true", help="Run synthetic probe validations")
    parser.add_argument("--minimum-lines", type=int, default=0, help="Optional minimum expected line count")
    parser.add_argument("--report-prefix", default="e2e_report", help="Generated report filename prefix")
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        context = CaeContext.create(manifest_path=args.manifest)
        log_file = resolve_log_file(context, args.log_file)
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
        reports_dir = context.path_value(
            cli_value=args.reports_dir,
            env_var=ENV_REPORTS_DIR,
            manifest_keys=("reports_dir",),
            default=context.repo_paths.reports_dir,
        )
        if log_file is None or goaccess_exe is None or profile_config is None or reports_dir is None:
            raise ValueError("log_file, goaccess_exe, profile_config, and reports_dir must resolve")

        verify_cae_pipeline(
            log_file=log_file,
            goaccess_exe=goaccess_exe,
            profile_config=profile_config,
            reports_dir=reports_dir,
            repo_root=context.repo_paths.repo_root,
            run_probes=args.run_probes,
            minimum_lines=args.minimum_lines,
            report_prefix=args.report_prefix,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
