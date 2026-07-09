#!/usr/bin/env python3
"""Self-tests for CAE pipeline verification helpers."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.verify.verify_cae_pipeline import load_goaccess_json, read_report_text


class VerifyCaePipelineTests(unittest.TestCase):
    def test_read_report_text_tolerates_non_utf8_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            report_path = Path(temp_dir_name) / "report.html"
            report_path.write_bytes(b"<html><title>CAE Log Statistics</title>\xd4</html>")

            text = read_report_text(report_path)

        self.assertIn("CAE Log Statistics", text)
        self.assertIn("\ufffd", text)

    def test_load_goaccess_json_tolerates_non_utf8_string_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            json_path = Path(temp_dir_name) / "goaccess.json"
            json_path.write_bytes(b'{"general":{"start_date":"29/6\xd4/2026"}}')

            parsed = load_goaccess_json(json_path)

        self.assertEqual(parsed["general"]["start_date"], "29/6\ufffd/2026")


if __name__ == "__main__":
    unittest.main()
