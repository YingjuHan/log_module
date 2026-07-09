#!/usr/bin/env python3
"""Self-tests for tools.cae_pipeline."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = TEST_ROOT.parent / "cae_log_module"
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from tools.pipeline.cae_pipeline import run_pipeline
from tools.tests.test_validate_cae_events import make_v1_row


class CaePipelineTests(unittest.TestCase):
    def test_pipeline_validates_config_log_and_writes_observability_exports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            input_log = temp_dir / "cae_events.jsonl"
            output_dir = temp_dir / "reports"
            input_log.write_text(json.dumps(make_v1_row(), separators=(",", ":")) + "\n", encoding="utf-8")

            result = run_pipeline(
                config_file=MODULE_ROOT / "config" / "cae_logger_config.ini",
                input_log=input_log,
                input_dir=None,
                output_log=None,
                output_dir=output_dir,
                prefix="sample",
                require_schema_version=True,
                require_columnar=False,
                observability=True,
            )

            self.assertEqual(result["line_count"], 1)
            self.assertTrue((output_dir / "sample.csv").is_file())
            self.assertTrue((output_dir / "sample_dag_nodes.csv").is_file())
            self.assertTrue((output_dir / "sample_rank_heatmap.csv").is_file())

    def test_pipeline_can_merge_fragments_before_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            input_dir = temp_dir / "fragments"
            output_dir = temp_dir / "reports"
            merged_log = temp_dir / "merged" / "cae_events.jsonl"
            input_dir.mkdir()
            row = make_v1_row()
            (input_dir / "cae_events_pid1.jsonl").write_text(
                json.dumps(row, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

            result = run_pipeline(
                config_file=MODULE_ROOT / "config" / "cae_logger_config.ini",
                input_log=None,
                input_dir=input_dir,
                output_log=merged_log,
                output_dir=output_dir,
                prefix="sample",
                require_schema_version=True,
                require_columnar=False,
                observability=False,
            )

            self.assertEqual(result["line_count"], 1)
            self.assertTrue(merged_log.is_file())
            self.assertTrue((output_dir / "sample.csv").is_file())


if __name__ == "__main__":
    unittest.main()
