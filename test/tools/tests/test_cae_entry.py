#!/usr/bin/env python3
"""Self-tests for the top-level CAE CLI dispatcher."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import cae


class CaeEntryTests(unittest.TestCase):
    def test_entry_options_before_command_are_forwarded(self) -> None:
        self.assertEqual(
            ["verify", "--manifest", "out/cae_manifest.json"],
            cae.normalize_entry_args(["--manifest", "out/cae_manifest.json", "verify"]),
        )

    def test_command_first_args_are_unchanged(self) -> None:
        self.assertEqual(
            ["verify", "--manifest", "out/cae_manifest.json"],
            cae.normalize_entry_args(["verify", "--manifest", "out/cae_manifest.json"]),
        )

    def test_build_commands_are_not_python_entry_points(self) -> None:
        self.assertNotIn("build", cae.COMMANDS)
        self.assertNotIn("test", cae.COMMANDS)
        self.assertNotIn("all", cae.COMMANDS)


if __name__ == "__main__":
    unittest.main()
