#!/usr/bin/env python3
"""Self-tests for post-process report generation."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.common.cae_env import CaeContext
from tools.reporting.run_postprocess_report import run_postprocess_report
from tools.tests.test_validate_cae_events import make_v1_row


class RunPostprocessReportTests(unittest.TestCase):
    def test_postprocess_writes_event_csv_into_reports_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            log_file = temp_dir / "cae_events.jsonl"
            report_dir = temp_dir / "reports"
            log_file.write_text(json.dumps(make_v1_row(), separators=(",", ":")) + "\n", encoding="utf-8")
            context = CaeContext.create(manifest_path=temp_dir / "missing_manifest.json")

            with mock.patch(
                "tools.reporting.run_postprocess_report.generate_reports",
                return_value=(report_dir / "report_en.html", report_dir / "report_zh.html"),
            ):
                result = run_postprocess_report(
                    context=context,
                    log_file_arg=str(log_file),
                    report_dir_arg=str(report_dir),
                    report_prefix="report",
                    export_prefix="cae_events",
                    require_columnar=False,
                )

            csv_path = report_dir / "cae_events.csv"
            self.assertEqual(result["export"]["csv_path"], csv_path)
            self.assertTrue(csv_path.is_file())
            with csv_path.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["schema_version"], "cae_event_v1")


if __name__ == "__main__":
    unittest.main()
