#!/usr/bin/env python3
"""Static contract tests for cae_logger documentation and install support."""

from __future__ import annotations

import unittest
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = TEST_ROOT.parent
MODULE_ROOT = WORKSPACE_ROOT / "cae_log_module"
TEST_PROJECT_ROOT = WORKSPACE_ROOT / "test"


class CaeLoggerDocsInstallContractTests(unittest.TestCase):
    def test_cmake_exposes_doxygen_and_test_project_install_options(self) -> None:
        cmake = (MODULE_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

        self.assertIn("option(CAE_LOGGER_BUILD_DOCS", cmake)
        self.assertIn("option(CAE_LOGGER_INSTALL_DOCS", cmake)
        self.assertIn("option(CAE_LOGGER_INSTALL_TEST_PROJECT", cmake)
        self.assertIn("find_package(Doxygen", cmake)
        self.assertIn("add_custom_target(cae_logger_docs", cmake)
        self.assertIn("cmake/Doxyfile.in", cmake)

    def test_doxyfile_includes_public_headers_and_markdown_sources(self) -> None:
        doxyfile = MODULE_ROOT / "cmake" / "Doxyfile.in"

        self.assertTrue(doxyfile.is_file())
        text = doxyfile.read_text(encoding="utf-8")
        for public_source in (
            "src/cae_logger.h",
            "src/cae_log_builder.h",
            "src/cae_logger_types.h",
            "src/cae_event_schema.h",
            "src/cae_task_scope.h",
            "src/cae_scoped_timer.h",
            "docs/user_document.md",
            "docs/cae_logger_macro_guide.md",
            "rule/cae_log_specification.md",
        ):
            self.assertIn(public_source, text)

        self.assertIn("USE_MDFILE_AS_MAINPAGE", text)
        self.assertIn("GENERATE_HTML", text)

    def test_install_rules_publish_html_only_and_test_source_project(self) -> None:
        cmake = (MODULE_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

        self.assertIn("${CMAKE_INSTALL_DOCDIR}/html", cmake)
        self.assertNotIn("${CMAKE_INSTALL_DOCDIR}/markdown", cmake)
        self.assertIn("${CMAKE_INSTALL_DATADIR}/cae_logger/test", cmake)
        self.assertIn("PATTERN \"build\" EXCLUDE", cmake)
        self.assertIn("PATTERN \"out\" EXCLUDE", cmake)
        self.assertIn("PATTERN \"__pycache__\" EXCLUDE", cmake)

    def test_installed_test_scripts_can_discover_adjacent_package_prefix(self) -> None:
        build_cmd = (TEST_PROJECT_ROOT / "build.cmd").read_text(encoding="utf-8")
        build_sh = (TEST_PROJECT_ROOT / "build.sh").read_text(encoding="utf-8")

        self.assertIn("INSTALL_PREFIX_CANDIDATE", build_cmd)
        self.assertIn("lib\\cmake\\cae_logger", build_cmd)
        self.assertIn("lib64\\cmake\\cae_logger", build_cmd)
        self.assertIn("install_prefix_candidate", build_sh)
        self.assertIn("lib/cmake/cae_logger", build_sh)
        self.assertIn("lib64/cmake/cae_logger", build_sh)


if __name__ == "__main__":
    unittest.main()
