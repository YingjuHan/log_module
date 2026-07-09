#!/usr/bin/env python3
"""Self-tests for tools.validate_cae_config."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.pipeline.validate_cae_config import validate_config


class ValidateCaeConfigTests(unittest.TestCase):
    def test_repo_default_config_is_valid_and_reports_reload_boundaries(self) -> None:
        report = validate_config(REPO_ROOT.parent / "cae_log_module" / "config" / "cae_logger_config.ini")

        self.assertTrue(report["valid"], report["errors"])
        self.assertIn("logger_health_interval_events", report["hot_reload_keys"])
        self.assertIn("async_queue_size", report["startup_only_keys"])

    def test_rejects_unknown_keys_bad_numbers_and_invalid_sampling_rate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            config = Path(temp_dir_name) / "cae_logger_config.ini"
            config.write_text(
                "thread_model = strange\n"
                "async_queue_size = 0\n"
                "call_chain_sample_rate = 1.5\n"
                "unknown_knob = true\n",
                encoding="utf-8",
            )

            report = validate_config(config)

            self.assertFalse(report["valid"])
            errors = "; ".join(report["errors"])
            self.assertIn("thread_model must be", errors)
            self.assertIn("async_queue_size must be greater than zero", errors)
            self.assertIn("call_chain_sample_rate must be between", errors)
            self.assertIn("unknown key: unknown_knob", errors)


if __name__ == "__main__":
    unittest.main()
