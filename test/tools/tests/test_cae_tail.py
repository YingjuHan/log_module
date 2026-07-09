#!/usr/bin/env python3
"""Self-tests for cae_tail filtering behavior."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.pipeline.cae_tail import load_and_filter
from tools.tests.test_validate_cae_events import make_v1_row


def args_for(path: Path, **overrides: object) -> argparse.Namespace:
    defaults = {
        "input": str(path),
        "module": None,
        "stage": None,
        "action": None,
        "level": None,
        "event_kind": None,
        "session": None,
        "min_duration_us": None,
        "contains": None,
        "trace_id": None,
        "event_id": None,
        "parent_event_id": None,
        "job_id": None,
        "node_id": None,
        "mpi_rank": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class CaeTailTests(unittest.TestCase):
    def test_load_and_filter_supports_schema_v1_identity_filters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            log_path = Path(temp_dir_name) / "cae_events.jsonl"
            parent = make_v1_row()
            parent.update({"event_id": "aaaaaaaaaaaaaaaa", "span_id": "aaaaaaaaaaaaaaaa", "job_id": "JOB-A", "node_id": "node-a", "mpi_rank": 0})
            child = make_v1_row()
            child.update(
                {
                    "event_id": "bbbbbbbbbbbbbbbb",
                    "span_id": "bbbbbbbbbbbbbbbb",
                    "parent_event_id": "aaaaaaaaaaaaaaaa",
                    "parent_span_id": "aaaaaaaaaaaaaaaa",
                    "job_id": "JOB-A",
                    "node_id": "node-b",
                    "mpi_rank": 1,
                }
            )
            log_path.write_text(json.dumps(parent) + "\n" + json.dumps(child) + "\n", encoding="utf-8")

            self.assertEqual([event["event_id"] for event in load_and_filter(args_for(log_path, event_id="bbbbbbbbbbbbbbbb"))], ["bbbbbbbbbbbbbbbb"])
            self.assertEqual([event["event_id"] for event in load_and_filter(args_for(log_path, parent_event_id="aaaaaaaaaaaaaaaa"))], ["bbbbbbbbbbbbbbbb"])
            self.assertEqual([event["event_id"] for event in load_and_filter(args_for(log_path, job_id="JOB-A", node_id="node-b", mpi_rank=1))], ["bbbbbbbbbbbbbbbb"])


if __name__ == "__main__":
    unittest.main()
