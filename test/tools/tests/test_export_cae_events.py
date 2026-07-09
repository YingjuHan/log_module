#!/usr/bin/env python3
"""Self-tests for tools.export_cae_events."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.pipeline.export_cae_events import export_cae_events
from tools.tests.test_validate_cae_events import make_v1_row


class ExportCaeEventsTests(unittest.TestCase):
    def test_export_writes_schema_json_and_csv_with_flattened_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            input_log = temp_dir / "cae_events.jsonl"
            output_dir = temp_dir / "out"
            row = make_v1_row()
            input_log.write_text(json.dumps(row, separators=(",", ":")) + "\n", encoding="utf-8")

            result = export_cae_events(input_log, output_dir, prefix="sample")

            schema_path = output_dir / "sample_schema.json"
            csv_path = output_dir / "sample.csv"
            self.assertEqual(result["rows"], 1)
            self.assertTrue(schema_path.is_file())
            self.assertTrue(csv_path.is_file())
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertEqual(schema["schema_version"], "cae_event_v1")
            with csv_path.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["schema_version"], "cae_event_v1")
            self.assertEqual(rows[0]["metric_residual"], "0.25")

    def test_export_flattens_logger_health_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            input_log = temp_dir / "cae_events.jsonl"
            output_dir = temp_dir / "out"
            row = make_v1_row()
            row.update(
                {
                    "component": "Logger",
                    "stage": "Runtime",
                    "action": "health_snapshot",
                    "event_type": "system",
                    "phase": "progress",
                    "domain": "system",
                    "entity_type": "logger",
                    "entity_name": "runtime_health",
                    "metrics": {
                        "records_emitted": 101,
                        "analysis_bytes_written": 4096,
                        "analysis_segments_created": 3,
                    },
                }
            )
            input_log.write_text(json.dumps(row, separators=(",", ":")) + "\n", encoding="utf-8")

            export_cae_events(input_log, output_dir, prefix="sample", pyarrow_module=None)

            with (output_dir / "sample.csv").open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["metric_records_emitted"], "101")
            self.assertEqual(rows[0]["metric_analysis_bytes_written"], "4096")
            self.assertEqual(rows[0]["metric_analysis_segments_created"], "3")

    def test_missing_pyarrow_is_skipped_unless_columnar_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            input_log = temp_dir / "cae_events.jsonl"
            output_dir = temp_dir / "out"
            input_log.write_text(json.dumps(make_v1_row(), separators=(",", ":")) + "\n", encoding="utf-8")

            result = export_cae_events(input_log, output_dir, prefix="sample", pyarrow_module=None)

            self.assertFalse(result["columnar_written"])
            self.assertIn("pyarrow", result["columnar_message"])
            with self.assertRaises(RuntimeError) as ctx:
                export_cae_events(input_log, output_dir, prefix="sample", require_columnar=True, pyarrow_module=None)
            self.assertIn("pyarrow is required", str(ctx.exception))

    def test_writes_parquet_and_arrow_when_pyarrow_is_available(self) -> None:
        class FakeTable:
            @classmethod
            def from_pylist(cls, rows: list[dict[str, object]]) -> "FakeTable":
                self = cls()
                self.rows = rows
                return self

        class FakeFeather:
            @staticmethod
            def write_feather(table: FakeTable, path: Path) -> None:
                path.write_text(f"arrow:{len(table.rows)}", encoding="utf-8")

        class FakeParquet:
            @staticmethod
            def write_table(table: FakeTable, path: Path) -> None:
                path.write_text(f"parquet:{len(table.rows)}", encoding="utf-8")

        class FakePyArrow:
            Table = FakeTable
            feather = FakeFeather
            parquet = FakeParquet

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            input_log = temp_dir / "cae_events.jsonl"
            output_dir = temp_dir / "out"
            input_log.write_text(json.dumps(make_v1_row(), separators=(",", ":")) + "\n", encoding="utf-8")

            result = export_cae_events(input_log, output_dir, prefix="sample", pyarrow_module=FakePyArrow)

            self.assertTrue(result["columnar_written"])
            self.assertTrue((output_dir / "sample.csv").is_file())
            self.assertEqual((output_dir / "sample.arrow").read_text(encoding="utf-8"), "arrow:1")
            self.assertEqual((output_dir / "sample.parquet").read_text(encoding="utf-8"), "parquet:1")

    @unittest.skipUnless(importlib.util.find_spec("pyarrow"), "pyarrow is not installed")
    def test_real_pyarrow_accepts_sparse_numeric_metric_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            input_log = temp_dir / "cae_events.jsonl"
            output_dir = temp_dir / "out"
            with_metric = make_v1_row()
            with_metric["metrics"] = {"residual": 0.25}
            without_metric = make_v1_row()
            without_metric.update({"event_id": "2222222222222222", "span_id": "2222222222222222", "sequence": 2})
            without_metric["metrics"] = {}
            input_log.write_text(
                json.dumps(with_metric, separators=(",", ":")) + "\n" +
                json.dumps(without_metric, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

            result = export_cae_events(input_log, output_dir, prefix="sample", require_columnar=True)

            self.assertTrue(result["columnar_written"])
            self.assertTrue((output_dir / "sample.csv").is_file())
            self.assertTrue((output_dir / "sample.arrow").is_file())
            self.assertTrue((output_dir / "sample.parquet").is_file())

    def test_observability_mode_writes_dag_timeline_heatmap_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            input_log = temp_dir / "cae_events.jsonl"
            output_dir = temp_dir / "out"
            root = make_v1_row()
            root.update({"event_id": "aaaaaaaaaaaaaaaa", "span_id": "aaaaaaaaaaaaaaaa", "sequence": 1, "logical_time": 1, "timestamp_epoch_us": 1000})
            child = make_v1_row()
            child.update(
                {
                    "event_id": "bbbbbbbbbbbbbbbb",
                    "span_id": "bbbbbbbbbbbbbbbb",
                    "parent_event_id": "aaaaaaaaaaaaaaaa",
                    "parent_span_id": "aaaaaaaaaaaaaaaa",
                    "sequence": 2,
                    "logical_time": 2,
                    "timestamp_epoch_us": 2000,
                }
            )
            input_log.write_text(
                json.dumps(root, separators=(",", ":")) + "\n" + json.dumps(child, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

            result = export_cae_events(input_log, output_dir, prefix="sample", observability=True, pyarrow_module=None)

            self.assertTrue((output_dir / "sample_dag_nodes.csv").is_file())
            self.assertTrue((output_dir / "sample_dag_edges.csv").is_file())
            self.assertTrue((output_dir / "sample_timeline.json").is_file())
            self.assertTrue((output_dir / "sample_rank_heatmap.csv").is_file())
            self.assertTrue((output_dir / "sample_observability_report.json").is_file())
            self.assertIn("observability_paths", result)
            with (output_dir / "sample_dag_edges.csv").open(encoding="utf-8", newline="") as fh:
                edge_rows = list(csv.DictReader(fh))
            self.assertIn("parent", {row["edge_type"] for row in edge_rows})

    def test_without_observability_mode_keeps_existing_export_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            input_log = temp_dir / "cae_events.jsonl"
            output_dir = temp_dir / "out"
            input_log.write_text(json.dumps(make_v1_row(), separators=(",", ":")) + "\n", encoding="utf-8")

            result = export_cae_events(input_log, output_dir, prefix="sample", pyarrow_module=None)

            self.assertNotIn("observability_paths", result)
            self.assertFalse((output_dir / "sample_dag_nodes.csv").exists())


if __name__ == "__main__":
    unittest.main()
