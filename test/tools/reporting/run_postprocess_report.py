#!/usr/bin/env python3
"""Generate post-process report artifacts from an existing merged CAE log."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.common.cae_env import CaeContext, ENV_REPORTS_DIR
from tools.pipeline.export_cae_events import export_cae_events
from tools.reporting.generate_reports import generate_reports, resolve_report_inputs
from tools.reporting.summarize_cae_report import write_summary_artifacts
from tools.verify.verify_cae_pipeline import resolve_log_file


def run_postprocess_report(
    *,
    context: CaeContext,
    log_file_arg: str | None,
    report_dir_arg: str | None,
    report_prefix: str,
    export_prefix: str,
    require_columnar: bool,
) -> dict[str, object]:
    """Generate HTML, summary, and tabular export artifacts into the reports directory."""
    log_file = resolve_log_file(context, log_file_arg)
    report_dir = context.path_value(
        cli_value=report_dir_arg,
        env_var=ENV_REPORTS_DIR,
        manifest_keys=("reports_dir",),
        default=context.repo_paths.reports_dir,
    )
    if report_dir is None:
        raise ValueError("report_dir must resolve to a directory")

    report_inputs = resolve_report_inputs(
        argparse.Namespace(
            manifest=str(context.manifest_path),
            log_file=str(log_file),
            report_dir=str(report_dir),
            prefix=report_prefix,
            profile_config=None,
            goaccess_exe=None,
            locale_dir=None,
            skip_locale_copy=False,
        ),
        repo=context.repo_paths,
    )
    reports = generate_reports(report_inputs)
    summary = write_summary_artifacts(
        input_path=log_file,
        output_dir=report_dir,
        alert_config_path=context.repo_paths.config_dir / "cae_alerts.json",
    )
    export = export_cae_events(
        Path(log_file),
        Path(report_dir),
        prefix=export_prefix,
        require_columnar=require_columnar,
    )
    return {
        "log_file": Path(log_file),
        "report_dir": Path(report_dir),
        "reports": reports,
        "summary": summary,
        "export": export,
    }


def main() -> None:
    """CLI entry point."""
    context = CaeContext.create(repo_paths=None)
    parser = argparse.ArgumentParser(
        description="Generate HTML reports and summary artifacts from an existing merged CAE log"
    )
    parser.add_argument("--manifest", default=str(context.manifest_path), help="Optional manifest JSON")
    parser.add_argument("--log-file", default=None, help="Merged CAE JSONL log file")
    parser.add_argument("--report-dir", default=None, help="Output directory for reports and summaries")
    parser.add_argument("--prefix", default="report", help="Report filename prefix")
    parser.add_argument("--export-prefix", default="cae_events", help="CSV/Arrow/Parquet export filename prefix")
    parser.add_argument("--require-columnar", action="store_true", help="Fail if Arrow/Parquet outputs cannot be written")
    args = parser.parse_args()

    try:
        context = CaeContext.create(manifest_path=args.manifest)
        print(">>> Generating GoAccess HTML reports from existing merged log...")
        print(">>> Generating summary artifacts from existing merged log...")
        print(">>> Exporting CSV/Arrow/Parquet artifacts from existing merged log...")
        result = run_postprocess_report(
            context=context,
            log_file_arg=args.log_file,
            report_dir_arg=args.report_dir,
            report_prefix=args.prefix,
            export_prefix=args.export_prefix,
            require_columnar=args.require_columnar,
        )
        export = result["export"]
        print(f"Wrote {export['schema_path']}")
        print(f"Wrote {export['csv_path']}")
        if export.get("arrow_path"):
            print(f"Wrote {export['arrow_path']}")
        if export.get("parquet_path"):
            print(f"Wrote {export['parquet_path']}")
        print(export["columnar_message"])
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        sys.exit(str(exc))

    print(">>> Post-process report generation completed.")
    print(f">>> Input log: {result['log_file']}")
    print(f">>> Output directory: {result['report_dir']}")


if __name__ == "__main__":
    main()
