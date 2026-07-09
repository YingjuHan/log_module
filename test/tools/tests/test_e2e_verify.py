#!/usr/bin/env python3
"""Self-tests for tools.e2e_verify."""

from __future__ import annotations

import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.common.cae_env import CaeContext, RepoPaths
from tools.verify.e2e_verify import launch_demo_quietly, resolve_build_logs_dir


class E2eVerifyTests(unittest.TestCase):
    def test_resolve_build_logs_dir_uses_manifest_app_config_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            repo = RepoPaths.from_repo_root(temp_dir_name)
            context = CaeContext(
                repo_paths=repo,
                manifest={"app": {"config_dir": "build/Debug"}},
                environ={},
                manifest_path=repo.manifest_path,
            )

            self.assertEqual(
                resolve_build_logs_dir(context),
                (Path(temp_dir_name) / "build" / "Debug" / "logs").resolve(strict=False),
            )

    def test_launch_demo_quietly_redirects_child_output(self) -> None:
        with mock.patch("tools.verify.e2e_verify.subprocess.Popen") as popen:
            launch_demo_quietly(["demo.exe", "Proc_1"], cwd="build/Debug")

        popen.assert_called_once()
        _, kwargs = popen.call_args
        self.assertEqual(kwargs["cwd"], "build/Debug")
        self.assertIs(kwargs["stdout"], __import__("subprocess").DEVNULL)
        self.assertIs(kwargs["stderr"], __import__("subprocess").STDOUT)


if __name__ == "__main__":
    unittest.main()
