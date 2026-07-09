#!/usr/bin/env python3
"""Self-tests for tools.validate_cae_events schema v1 behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.pipeline.validate_cae_events import validate_jsonl_item


def make_patch3_row() -> dict[str, object]:
    return {
        "timestamp": "2026-06-08T10:00:01.000",
        "date": "2026-06-08",
        "time": "10:00:01",
        "source": "pid:probe/tid:1",
        "component": "Solver",
        "stage": "Iteration",
        "action": "nonlinear_step",
        "level": "INFO",
        "message": "Nonlinear iteration completed.",
        "event_kind": "point",
        "duration_us": 0,
        "size": 31,
        "session": "Proc_1",
        "thread_name": "SolverWorker",
        "sequence": 1,
        "trace_id": "feedfacefeedfacefeedfacefeedface",
        "span_id": "1111111111111111",
        "parent_span_id": None,
        "object_type": None,
        "object_name": None,
        "result": "completed",
        "reason": None,
        "node_id": "node-a",
        "mpi_rank": 0,
        "metrics": {"residual": 0.25},
    }


def make_v1_row() -> dict[str, object]:
    row = make_patch3_row()
    row.update(
        {
            "schema_version": "cae_event_v1",
            "event_id": "1111111111111111",
            "parent_event_id": None,
            "event_type": "solve",
            "phase": "progress",
            "domain": "cfd",
            "entity_type": "solver",
            "entity_name": "nonlinear_loop",
            "job_id": "JOB-2026-001",
            "global_sequence_id": "JOB-2026-001:node-a:0:1",
            "logical_time": 1,
            "timestamp_epoch_us": 1780884001000000,
            "monotonic_us": 250,
        }
    )
    return row


class ValidateCaeEventsTests(unittest.TestCase):
    def test_patch3_structured_rows_remain_valid_by_default(self) -> None:
        self.assertEqual(validate_jsonl_item(make_patch3_row()), [])

    def test_schema_v1_rows_are_valid_when_required(self) -> None:
        self.assertEqual(validate_jsonl_item(make_v1_row(), require_schema_version="cae_event_v1"), [])

    def test_require_schema_version_rejects_missing_v1_fields(self) -> None:
        errors = validate_jsonl_item(make_patch3_row(), require_schema_version="cae_event_v1")

        self.assertIn("schema_version must be 'cae_event_v1'", errors)
        self.assertIn("event_id must be a non-empty string", errors)
        self.assertIn("timestamp_epoch_us must be an integer", errors)

    def test_schema_v1_rejects_invalid_enum_values(self) -> None:
        row = make_v1_row()
        row["event_type"] = "http_request"
        row["phase"] = "maybe"
        row["domain"] = "unknown_domain"

        errors = validate_jsonl_item(row, require_schema_version="cae_event_v1")

        self.assertIn("event_type must be one of:", "; ".join(errors))
        self.assertIn("phase must be one of:", "; ".join(errors))
        self.assertIn("domain must be one of:", "; ".join(errors))

    def test_event_parent_aliases_must_match_span_aliases(self) -> None:
        row = make_v1_row()
        row["parent_span_id"] = "2222222222222222"
        row["parent_event_id"] = "3333333333333333"

        errors = validate_jsonl_item(row, require_schema_version="cae_event_v1")

        self.assertIn("parent_event_id must match parent_span_id when both are present", errors)

    def test_logical_and_timestamp_fields_must_be_non_negative(self) -> None:
        row = make_v1_row()
        row["logical_time"] = -1
        row["timestamp_epoch_us"] = -10
        row["monotonic_us"] = -20

        errors = validate_jsonl_item(row, require_schema_version="cae_event_v1")

        self.assertIn("logical_time must be non-negative", errors)
        self.assertIn("timestamp_epoch_us must be non-negative", errors)
        self.assertIn("monotonic_us must be non-negative", errors)


if __name__ == "__main__":
    unittest.main()
