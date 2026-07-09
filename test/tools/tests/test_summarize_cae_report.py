#!/usr/bin/env python3
"""Self-tests for CAE summary graph statistics."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.reporting.summarize_cae_report import build_summary
from tools.tests.test_cae_event_graph import event


class SummarizeCaeReportTests(unittest.TestCase):
    def test_build_summary_includes_dag_stats(self) -> None:
        events = [
            event("aaaaaaaaaaaaaaaa", sequence=1, logical_time=1, timestamp_epoch_us=1000, mpi_rank=0),
            event("bbbbbbbbbbbbbbbb", parent_event_id="aaaaaaaaaaaaaaaa", sequence=2, logical_time=2, timestamp_epoch_us=2000, mpi_rank=0),
            event("cccccccccccccccc", sequence=1, logical_time=1, timestamp_epoch_us=1500, mpi_rank=1),
        ]
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            summary = build_summary(events, temp_dir / "events.jsonl", temp_dir / "alerts.json")

        dag_stats = summary["dag_stats"]
        self.assertEqual(dag_stats["node_count"], 3)
        self.assertGreaterEqual(dag_stats["edge_count"], 2)
        self.assertEqual(dag_stats["orphan_count"], 0)
        self.assertEqual(dag_stats["per_rank_event_counts"]["JOB-2026-001:node-a:0"], 2)
        self.assertEqual(dag_stats["per_rank_event_counts"]["JOB-2026-001:node-a:1"], 1)
        self.assertGreaterEqual(dag_stats["max_rank_local_gap_us"], 1000)

    def test_build_summary_includes_latest_logger_health(self) -> None:
        first = event("aaaaaaaaaaaaaaaa", sequence=1, logical_time=1, timestamp_epoch_us=1000)
        first.update(
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
                    "records_emitted": 50,
                    "analysis_bytes_written": 2048,
                    "analysis_segments_created": 1,
                },
            }
        )
        latest = event("bbbbbbbbbbbbbbbb", sequence=2, logical_time=2, timestamp_epoch_us=2000)
        latest.update(
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
                    "async_queue_size": 4096,
                    "async_thread_count": 1,
                },
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            summary = build_summary([first, latest], temp_dir / "events.jsonl", temp_dir / "alerts.json")

        logger_health = summary["logger_health"]
        self.assertEqual(logger_health["health_event_count"], 2)
        self.assertEqual(logger_health["latest_metrics"]["records_emitted"], 101)
        self.assertEqual(logger_health["latest_metrics"]["analysis_bytes_written"], 4096)
        self.assertEqual(logger_health["segments_created"], 3)
        self.assertEqual(logger_health["latest_sequence"], 2)


if __name__ == "__main__":
    unittest.main()
