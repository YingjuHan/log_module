#!/usr/bin/env python3
"""Self-tests for tools.merge_cae_logs."""

from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.pipeline.merge_cae_logs import merge_cae_logs
from tools.tests.test_validate_cae_events import make_v1_row


class MergeCaeLogsTests(unittest.TestCase):
    def test_merge_and_copy_module_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "build" / "Debug" / "logs"
            output_log = root / "logs" / "cae_events.jsonl"
            copy_dir = root / "logs"
            input_dir.mkdir(parents=True)

            first = make_v1_row()
            first.update({"timestamp_epoch_us": 100, "logical_time": 1, "sequence": 1, "message": "first"})
            second = make_v1_row()
            second.update({"timestamp_epoch_us": 200, "logical_time": 2, "sequence": 2, "message": "second"})
            third = make_v1_row()
            third.update({"timestamp_epoch_us": 300, "logical_time": 3, "sequence": 3, "message": "third"})

            (input_dir / "cae_events_proc1.jsonl").write_text(json.dumps(first) + "\n", encoding="utf-8")
            (input_dir / "cae_events_proc2.jsonl").write_text(
                json.dumps(second) + "\n" + json.dumps(third) + "\n",
                encoding="utf-8",
            )
            (input_dir / "Mesh.log").write_text("mesh\n", encoding="utf-8")

            result = merge_cae_logs(
                input_dir=input_dir,
                output_log=output_log,
                copy_module_logs_to=copy_dir,
            )

            self.assertEqual(result["line_count"], 3)
            messages = [json.loads(line)["message"] for line in output_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(messages, ["first", "second", "third"])
            self.assertTrue((copy_dir / "Mesh.log").is_file())
            self.assertTrue((output_log.with_suffix(".merge_report.json")).is_file())

    def test_unknown_json_object_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "logs"
            input_dir.mkdir(parents=True)

            (input_dir / "cae_events_bad.jsonl").write_text('{"foo":1}\n', encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                merge_cae_logs(input_dir=input_dir, output_log=root / "merged" / "cae_events.jsonl")

            self.assertIn("Invalid CAE event log rows", str(ctx.exception))
            self.assertIn("timestamp must be a non-empty string", str(ctx.exception))

    def test_non_object_json_rows_are_rejected(self) -> None:
        payloads = (
            ("array", "[1,2,3]\n"),
            ("number", "42\n"),
        )

        for label, payload in payloads:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    input_dir = root / "logs"
                    input_dir.mkdir(parents=True)

                    (input_dir / "cae_events_bad.jsonl").write_text(payload, encoding="utf-8")

                    with self.assertRaises(ValueError) as ctx:
                        merge_cae_logs(input_dir=input_dir, output_log=root / "merged" / "cae_events.jsonl")

                    self.assertIn("row is not a JSON object", str(ctx.exception))

    def test_merge_defaults_to_causal_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "logs"
            output_log = root / "merged" / "cae_events.jsonl"
            input_dir.mkdir(parents=True)

            late_rank0 = make_v1_row()
            late_rank0.update({"timestamp_epoch_us": 300, "logical_time": 3, "node_id": "node-a", "mpi_rank": 0, "sequence": 2, "message": "late"})
            early_rank1 = make_v1_row()
            early_rank1.update({"timestamp_epoch_us": 100, "logical_time": 1, "node_id": "node-b", "mpi_rank": 1, "sequence": 1, "message": "early"})
            mid_rank0 = make_v1_row()
            mid_rank0.update({"timestamp_epoch_us": 200, "logical_time": 2, "node_id": "node-a", "mpi_rank": 0, "sequence": 1, "message": "middle"})

            (input_dir / "cae_events_pid2.jsonl").write_text(json.dumps(late_rank0) + "\n" + json.dumps(mid_rank0) + "\n", encoding="utf-8")
            (input_dir / "cae_events_pid1.jsonl").write_text(json.dumps(early_rank1) + "\n", encoding="utf-8")

            result = merge_cae_logs(input_dir=input_dir, output_log=output_log)

            messages = [json.loads(line)["message"] for line in output_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(messages, ["early", "middle", "late"])
            self.assertEqual(result["ordering"], "causal")
            report = json.loads(output_log.with_suffix(".merge_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["ordering"], "causal")
            self.assertEqual(report["line_count"], 3)

    def test_parent_event_precedes_child_even_when_timestamp_is_later(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "logs"
            output_log = root / "merged" / "cae_events.jsonl"
            input_dir.mkdir(parents=True)

            child = make_v1_row()
            child.update(
                {
                    "event_id": "bbbbbbbbbbbbbbbb",
                    "span_id": "bbbbbbbbbbbbbbbb",
                    "parent_event_id": "aaaaaaaaaaaaaaaa",
                    "parent_span_id": "aaaaaaaaaaaaaaaa",
                    "timestamp_epoch_us": 100,
                    "logical_time": 1,
                    "sequence": 1,
                    "message": "child",
                }
            )
            parent = make_v1_row()
            parent.update(
                {
                    "event_id": "aaaaaaaaaaaaaaaa",
                    "span_id": "aaaaaaaaaaaaaaaa",
                    "parent_event_id": None,
                    "parent_span_id": None,
                    "timestamp_epoch_us": 200,
                    "logical_time": 2,
                    "sequence": 2,
                    "message": "parent",
                }
            )
            (input_dir / "cae_events_pid1.jsonl").write_text(
                json.dumps(child) + "\n" + json.dumps(parent) + "\n",
                encoding="utf-8",
            )

            merge_cae_logs(input_dir=input_dir, output_log=output_log)

            messages = [json.loads(line)["message"] for line in output_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(messages, ["parent", "child"])
            report = json.loads(output_log.with_suffix(".merge_report.json").read_text(encoding="utf-8"))
            self.assertTrue(report["causal_reordered"])
            self.assertEqual(report["causal_parent_edges"], 1)

    def test_preserve_file_order_keeps_fragment_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "logs"
            output_log = root / "merged" / "cae_events.jsonl"
            input_dir.mkdir(parents=True)

            late = make_v1_row()
            late.update({"timestamp_epoch_us": 300, "message": "late"})
            early = make_v1_row()
            early.update({"timestamp_epoch_us": 100, "message": "early"})
            (input_dir / "cae_events_a.jsonl").write_text(json.dumps(late) + "\n", encoding="utf-8")
            (input_dir / "cae_events_b.jsonl").write_text(json.dumps(early) + "\n", encoding="utf-8")

            result = merge_cae_logs(input_dir=input_dir, output_log=output_log, preserve_file_order=True)

            messages = [json.loads(line)["message"] for line in output_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(messages, ["late", "early"])
            self.assertEqual(result["ordering"], "file")

    def test_rotated_segment_files_merge_in_causal_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "logs"
            output_log = root / "merged" / "cae_events.jsonl"
            input_dir.mkdir(parents=True)

            segment0 = make_v1_row()
            segment0.update({"timestamp_epoch_us": 300, "logical_time": 3, "sequence": 3, "message": "segment-0"})
            segment1 = make_v1_row()
            segment1.update({"timestamp_epoch_us": 100, "logical_time": 1, "sequence": 1, "message": "segment-1"})
            segment2 = make_v1_row()
            segment2.update({"timestamp_epoch_us": 200, "logical_time": 2, "sequence": 2, "message": "segment-2"})

            (input_dir / "cae_events_pid42.jsonl").write_text(json.dumps(segment0) + "\n", encoding="utf-8")
            (input_dir / "cae_events_pid42_000001.jsonl").write_text(json.dumps(segment1) + "\n", encoding="utf-8")
            (input_dir / "cae_events_pid42_000002.jsonl").write_text(json.dumps(segment2) + "\n", encoding="utf-8")

            result = merge_cae_logs(input_dir=input_dir, output_log=output_log)

            messages = [json.loads(line)["message"] for line in output_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(messages, ["segment-1", "segment-2", "segment-0"])
            self.assertEqual(result["line_count"], 3)
            report = json.loads(output_log.with_suffix(".merge_report.json").read_text(encoding="utf-8"))
            self.assertEqual(len(report["event_logs"]), 3)

    def test_missing_event_logs_error_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "logs"
            input_dir.mkdir()

            with self.assertRaises(FileNotFoundError) as ctx:
                merge_cae_logs(input_dir=input_dir, output_log=Path(temp_dir) / "out.jsonl")

            self.assertIn("No CAE event logs found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
