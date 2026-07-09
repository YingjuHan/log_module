#!/usr/bin/env python3
"""Self-tests for shared CAE environment helpers."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.common.cae_env import (
    cmake_build_dir_needs_fresh_configure,
    cmake_configure_command,
    default_spdlog_package_dir,
    generator_for_toolchain,
    merge_build_type_option_for_build_dir,
    resolve_cmake_generator_choice,
    should_pass_config_for_build_dir,
)


class CaeEnvTests(unittest.TestCase):
    def test_toolchain_category_maps_to_generator(self) -> None:
        self.assertEqual("MinGW Makefiles", generator_for_toolchain("mingw"))
        self.assertEqual("Unix Makefiles", generator_for_toolchain("gcc"))

    def test_explicit_generator_takes_precedence_over_toolchain(self) -> None:
        self.assertEqual("Ninja", resolve_cmake_generator_choice("Ninja", "MINGW"))

    def test_default_spdlog_package_dir_does_not_use_external_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            external_spdlog = Path(temp_dir) / "spdlog" / "out" / "lib" / "cmake" / "spdlog"
            external_spdlog.mkdir(parents=True)
            (external_spdlog / "spdlogConfig.cmake").write_text("", encoding="utf-8")

            self.assertIsNone(default_spdlog_package_dir(repo_root))

    def test_single_config_cache_uses_build_type_instead_of_config_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = Path(temp_dir) / "build"
            build_dir.mkdir()
            (build_dir / "CMakeCache.txt").write_text(
                "CMAKE_GENERATOR:INTERNAL=Ninja\n",
                encoding="utf-8",
            )

            self.assertFalse(should_pass_config_for_build_dir(build_dir, None, "Debug"))
            self.assertIn(
                ("CMAKE_BUILD_TYPE", "Debug"),
                merge_build_type_option_for_build_dir([], build_dir, None, "Debug"),
            )

    def test_multi_config_cache_uses_config_flag_without_build_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = Path(temp_dir) / "build"
            build_dir.mkdir()
            (build_dir / "CMakeCache.txt").write_text(
                "\n".join(
                    (
                        "CMAKE_GENERATOR:INTERNAL=Ninja Multi-Config",
                        "CMAKE_CONFIGURATION_TYPES:STRING=Debug;Release;MinSizeRel;RelWithDebInfo",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            self.assertTrue(should_pass_config_for_build_dir(build_dir, "Ninja Multi-Config", "Debug"))
            self.assertEqual(
                [],
                merge_build_type_option_for_build_dir([], build_dir, "Ninja Multi-Config", "Debug"),
            )

    def test_generator_mismatch_uses_requested_generator_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_dir = root / "build"
            source_dir = root / "src"
            build_dir.mkdir()
            source_dir.mkdir()
            (build_dir / "CMakeCache.txt").write_text(
                "\n".join(
                    (
                        "CMAKE_GENERATOR:INTERNAL=Ninja Multi-Config",
                        "CMAKE_CONFIGURATION_TYPES:STRING=Debug;Release;MinSizeRel;RelWithDebInfo",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            self.assertTrue(cmake_build_dir_needs_fresh_configure(build_dir, "Ninja"))
            self.assertFalse(should_pass_config_for_build_dir(build_dir, "Ninja", "Debug"))
            self.assertIn(
                ("CMAKE_BUILD_TYPE", "Debug"),
                merge_build_type_option_for_build_dir([], build_dir, "Ninja", "Debug"),
            )
            self.assertEqual(
                ["cmake", "--fresh", "-G", "Ninja", "-S", str(source_dir), "-B", str(build_dir)],
                cmake_configure_command(
                    source_dir=source_dir,
                    build_dir=build_dir,
                    generator="Ninja",
                    fresh=True,
                ),
            )


if __name__ == "__main__":
    unittest.main()
