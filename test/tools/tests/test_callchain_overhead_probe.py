#!/usr/bin/env python3
"""Self-tests for tools.callchain_overhead_probe."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.runtime.callchain_overhead_probe import build_callchain_overhead_report
from tools.tests.test_validate_cae_events import make_v1_row


class CallchainOverheadProbeTests(unittest.TestCase):
    def test_summarizes_status_counts_and_span_durations(self) -> None:
        captured = make_v1_row()
        captured.update(
            {
                "event_kind": "span",
                "duration_us": 100,
                "call_chain_status": "captured",
                "level": "ERROR",
            }
        )
        skipped = make_v1_row()
        skipped.update(
            {
                "event_id": "2222222222222222",
                "span_id": "2222222222222222",
                "event_kind": "span",
                "duration_us": 300,
                "call_chain_status": "disabled",
                "level": "INFO",
            }
        )

        report = build_callchain_overhead_report([captured, skipped])

        self.assertEqual(report["event_count"], 2)
        self.assertEqual(report["call_chain_status_counts"]["captured"], 1)
        self.assertEqual(report["call_chain_status_counts"]["disabled"], 1)
        self.assertEqual(report["capture_rate"], 0.5)
        self.assertEqual(report["span_duration_by_call_chain_status"]["captured"]["p50_duration_us"], 100)
        self.assertEqual(report["level_status_counts"]["ERROR"]["captured"], 1)


if __name__ == "__main__":
    unittest.main()
