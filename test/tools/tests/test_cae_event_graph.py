#!/usr/bin/env python3
"""Self-tests for CAE event graph/timeline artifact generation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.pipeline.cae_event_graph import build_observability_artifacts
from tools.tests.test_validate_cae_events import make_patch3_row, make_v1_row


def event(
    event_id: str,
    *,
    parent_event_id: str | None = None,
    trace_id: str = "feedfacefeedfacefeedfacefeedface",
    job_id: str = "JOB-2026-001",
    node_id: str = "node-a",
    mpi_rank: int = 0,
    sequence: int = 1,
    logical_time: int = 1,
    timestamp_epoch_us: int = 1_780_884_001_000_000,
    duration_us: int = 0,
    event_kind: str = "point",
) -> dict[str, object]:
    row = make_v1_row()
    row.update(
        {
            "event_id": event_id,
            "span_id": event_id,
            "parent_event_id": parent_event_id,
            "parent_span_id": parent_event_id,
            "trace_id": trace_id,
            "job_id": job_id,
            "node_id": node_id,
            "mpi_rank": mpi_rank,
            "sequence": sequence,
            "global_sequence_id": f"{job_id}:{node_id}:{mpi_rank}:{sequence}",
            "logical_time": logical_time,
            "timestamp_epoch_us": timestamp_epoch_us,
            "monotonic_us": sequence * 100,
            "duration_us": duration_us,
            "event_kind": event_kind,
            "message": event_id,
        }
    )
    return row


class CaeEventGraphTests(unittest.TestCase):
    def test_builds_parent_trace_and_rank_edges(self) -> None:
        artifacts = build_observability_artifacts(
            [
                event("aaaaaaaaaaaaaaaa", sequence=1, logical_time=1, timestamp_epoch_us=1000),
                event("bbbbbbbbbbbbbbbb", parent_event_id="aaaaaaaaaaaaaaaa", sequence=2, logical_time=2, timestamp_epoch_us=2000),
                event("cccccccccccccccc", parent_event_id="aaaaaaaaaaaaaaaa", sequence=3, logical_time=3, timestamp_epoch_us=3000),
            ]
        )

        edge_keys = {
            (edge["source_event_id"], edge["target_event_id"], edge["edge_type"])
            for edge in artifacts["edges"]
        }
        self.assertIn(("aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb", "parent"), edge_keys)
        self.assertIn(("aaaaaaaaaaaaaaaa", "cccccccccccccccc", "parent"), edge_keys)
        self.assertIn(("aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb", "trace_sequence"), edge_keys)
        self.assertIn(("bbbbbbbbbbbbbbbb", "cccccccccccccccc", "trace_sequence"), edge_keys)
        self.assertIn(("aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb", "rank_sequence"), edge_keys)
        self.assertEqual(len(artifacts["nodes"]), 3)

    def test_reports_duplicate_missing_parent_cross_job_and_inversions(self) -> None:
        artifacts = build_observability_artifacts(
            [
                event("dddddddddddddddd", sequence=1, logical_time=2, timestamp_epoch_us=2000),
                event("dddddddddddddddd", sequence=2, logical_time=3, timestamp_epoch_us=3000),
                event("eeeeeeeeeeeeeeee", parent_event_id="ffffffffffffffff", sequence=3, logical_time=4, timestamp_epoch_us=4000),
                event("abababababababab", parent_event_id="cdcdcdcdcdcdcdcd", sequence=4, logical_time=5, timestamp_epoch_us=5000),
                event("cdcdcdcdcdcdcdcd", job_id="JOB-OTHER", sequence=5, logical_time=6, timestamp_epoch_us=6000),
                event("fefefefefefefefe", sequence=6, logical_time=1, timestamp_epoch_us=1000),
            ]
        )

        warning_codes = {warning["code"] for warning in artifacts["warnings"]}
        self.assertIn("duplicate_event_id", warning_codes)
        self.assertIn("missing_parent_event", warning_codes)
        self.assertIn("cross_job_parent_edge", warning_codes)
        self.assertIn("trace_sequence_inversion", warning_codes)
        self.assertIn("rank_sequence_inversion", warning_codes)

    def test_builds_multi_rank_heatmap_buckets_and_warns_on_enriched_legacy_rows(self) -> None:
        legacy = make_patch3_row()
        legacy.update({"event_id": None, "job_id": "Proc_1", "node_id": "node-a", "mpi_rank": 0})
        artifacts = build_observability_artifacts(
            [
                event("1111111111111111", mpi_rank=0, timestamp_epoch_us=1_000_000, duration_us=10, event_kind="span"),
                event("2222222222222222", mpi_rank=0, timestamp_epoch_us=1_500_000, duration_us=20, event_kind="span"),
                event("3333333333333333", mpi_rank=1, timestamp_epoch_us=1_500_000, duration_us=0, event_kind="point"),
                legacy,
            ],
            bucket_ms=1000,
        )

        heatmap = {
            (row["mpi_rank"], row["time_bucket_ms"]): row
            for row in artifacts["heatmap_rows"]
        }
        self.assertEqual(heatmap[(0, 1000)]["event_count"], 2)
        self.assertEqual(heatmap[(0, 1000)]["span_count"], 2)
        self.assertEqual(heatmap[(0, 1000)]["duration_us_sum"], 30)
        self.assertEqual(heatmap[(1, 1000)]["event_count"], 1)
        self.assertIn("incomplete_graph_identity", {warning["code"] for warning in artifacts["warnings"]})


if __name__ == "__main__":
    unittest.main()
