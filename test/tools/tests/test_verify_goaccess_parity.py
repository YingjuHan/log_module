#!/usr/bin/env python3
"""Self-tests for tools.verify_goaccess_parity."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.verify import verify_goaccess_parity


class VerifyGoaccessParityTests(unittest.TestCase):
    def test_default_paths_follow_split_project_layout(self) -> None:
        test_root = Path(__file__).resolve().parents[2]
        workspace_root = test_root.parent

        args = verify_goaccess_parity.build_argument_parser().parse_args([])

        self.assertEqual(Path(args.source_dir), workspace_root / "goaccess")
        self.assertEqual(Path(args.cmake_config), workspace_root / "goaccess" / "build" / "Debug" / "config.h")
        self.assertEqual(Path(args.reference_build_dir), test_root / "build" / "goaccess_autotools_ref")

    def test_prepare_reference_build_dir_falls_back_when_cleanup_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name)
            reference_dir = root / "goaccess_autotools_ref"
            reference_dir.mkdir()

            calls: list[str] = []

            def denied_rmtree(path: str) -> None:
                calls.append(path)
                raise PermissionError("access denied")

            prepared = verify_goaccess_parity.prepare_reference_build_dir(
                str(reference_dir),
                clean=True,
                rmtree=denied_rmtree,
                unique_suffix="fresh",
            )

            self.assertEqual(calls, [str(reference_dir)])
            self.assertEqual(prepared, str(root / "goaccess_autotools_ref_fresh"))
            self.assertFalse(Path(prepared).exists())

    def test_nls_disabled_differences_are_allowed(self) -> None:
        reference = {
            "ENABLE_NLS": "1",
            "HAVE_DCGETTEXT": "1",
            "HAVE_GETTEXT": "1",
            "HAVE_ICONV": "1",
            "HAVE_LIBINTL": "1",
        }
        current: dict[str, str] = {}

        matches, exceptions, diffs = verify_goaccess_parity.compare_macros(
            reference,
            current,
            extra_exceptions=verify_goaccess_parity.nls_disabled_exceptions({"ENABLE_NLS": "OFF"}),
        )

        self.assertEqual(matches, [])
        self.assertEqual(diffs, [])
        self.assertEqual(len(exceptions), len(reference))


if __name__ == "__main__":
    unittest.main()
