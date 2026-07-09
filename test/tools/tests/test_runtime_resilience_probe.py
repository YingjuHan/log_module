#!/usr/bin/env python3
"""Self-tests for tools.runtime_resilience_probe."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.runtime.runtime_resilience_probe import (
    assert_resilience_artifacts,
    count_logger_health_events,
    upsert_config_key,
)
from tools.tests.test_validate_cae_events import make_v1_row


class RuntimeResilienceProbeTests(unittest.TestCase):
    def test_upsert_config_key_replaces_existing_or_appends_missing_key(self) -> None:
        original = "io_mode = Async\nanalysis_log_max_bytes = 100\n"

        updated = upsert_config_key(original, "analysis_log_max_bytes", "4096")
        updated = upsert_config_key(updated, "logger_health_interval_events", "10")

        self.assertIn("analysis_log_max_bytes = 4096", updated)
        self.assertNotIn("analysis_log_max_bytes = 100", updated)
        self.assertTrue(updated.endswith("logger_health_interval_events = 10\n"))

    def test_assert_resilience_artifacts_accepts_rotated_logs_and_health_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            logs_dir = temp_dir / "logs"
            reports_dir = temp_dir / "reports"
            logs_dir.mkdir()
            reports_dir.mkdir()
            base_log = logs_dir / "cae_events_pid42.jsonl"
            rotated_log = logs_dir / "cae_events_pid42_000001.jsonl"
            merged_log = temp_dir / "cae_events.jsonl"
            summary_path = reports_dir / "cae_summary.json"
            export_csv = reports_dir / "cae_events.csv"

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
                    "metrics": {"analysis_segments_created": 2},
                }
            )
            payload = json.dumps(row, separators=(",", ":")) + "\n"
            base_log.write_text(payload, encoding="utf-8")
            rotated_log.write_text(payload, encoding="utf-8")
            merged_log.write_text(payload, encoding="utf-8")
            summary_path.write_text(
                json.dumps({"logger_health": {"health_event_count": 1, "segments_created": 2}}),
                encoding="utf-8",
            )
            export_csv.write_text("schema_version\ncae_event_v1\n", encoding="utf-8")

            assert_resilience_artifacts(logs_dir, reports_dir, merged_log, prefix="cae_events")

    def test_count_logger_health_events_ignores_non_health_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            path = Path(temp_dir_name) / "events.jsonl"
            normal = make_v1_row()
            health = make_v1_row()
            health.update({"component": "Logger", "action": "health_snapshot"})
            path.write_text(
                json.dumps(normal, separators=(",", ":")) + "\n"
                + json.dumps(health, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

            self.assertEqual(count_logger_health_events(path), 1)


if __name__ == "__main__":
    unittest.main()
