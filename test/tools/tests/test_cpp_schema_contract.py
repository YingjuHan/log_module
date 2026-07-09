#!/usr/bin/env python3
"""Static contract tests for the C++ CAE schema API surface."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = TEST_ROOT.parent
MODULE_ROOT = WORKSPACE_ROOT / "cae_log_module"
GOACCESS_ROOT = WORKSPACE_ROOT / "goaccess"
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from tools.pipeline.cae_event_schema import SCHEMA_REGISTRY_PATH


class CppSchemaContractTests(unittest.TestCase):
    def test_public_headers_split_classes_and_preserve_umbrella_api(self) -> None:
        umbrella = (MODULE_ROOT / "src" / "cae_logger.h").read_text(encoding="utf-8")
        builder = (MODULE_ROOT / "src" / "cae_log_builder.h").read_text(encoding="utf-8")
        task_scope = (MODULE_ROOT / "src" / "cae_task_scope.h").read_text(encoding="utf-8")
        scoped_timer = (MODULE_ROOT / "src" / "cae_scoped_timer.h").read_text(encoding="utf-8")

        self.assertIn('#include "cae_event_schema.h"', umbrella)
        self.assertIn('#include "cae_log_builder.h"', umbrella)
        self.assertIn('#include "cae_task_scope.h"', umbrella)
        self.assertIn('#include "cae_scoped_timer.h"', umbrella)
        self.assertIn("LogBuilder& event_type(EventType theEventType);", builder)
        self.assertIn("LogBuilder& phase(EventPhase thePhase);", builder)
        self.assertIn("LogBuilder& domain(Domain theDomain);", builder)
        self.assertIn("LogBuilder& duration_us(std::uint64_t theDurationUs);", builder)
        self.assertIn(
            "LogBuilder& entity(const char* theEntityType, const char* theEntityName);",
            builder,
        )
        self.assertIn("class CAE_LOGGER_EXPORT TaskScope", task_scope)
        self.assertIn("class CAE_LOGGER_EXPORT ScopedTimer", scoped_timer)
        self.assertIn(
            "CAE_LOGGER_EXPORT void set_job_id(const std::string& theJobId);",
            umbrella,
        )
        self.assertIn(
            "CAE_LOGGER_EXPORT void set_logical_time(std::uint64_t theLogicalTime);",
            umbrella,
        )

    def test_public_logger_header_removes_legacy_text_log_entrypoints(self) -> None:
        umbrella = (MODULE_ROOT / "src" / "cae_logger.h").read_text(encoding="utf-8")
        core_header = (MODULE_ROOT / "src" / "cae_logger_core.h").read_text(encoding="utf-8")
        logger_api = (MODULE_ROOT / "src" / "cae_logger.cpp").read_text(encoding="utf-8")
        core_impl = (MODULE_ROOT / "src" / "cae_logger_core.cpp").read_text(encoding="utf-8")
        detail_impl = (MODULE_ROOT / "src" / "cae_logger_detail.cpp").read_text(encoding="utf-8")

        self.assertNotIn("_log_impl", umbrella)
        self.assertNotIn("_log_impl", logger_api)
        self.assertNotIn("_log_impl", detail_impl)
        self.assertNotIn("emit_legacy", core_header)
        self.assertNotIn("emit_legacy", core_impl)
        self.assertNotIn("CAE_LOG_DETAIL_LOG_DISPATCH", umbrella)
        self.assertNotIn("CAE_LOG_DETAIL_DUR_DISPATCH", umbrella)

    def test_public_logger_header_keeps_chain_macros_without_level_shortcuts(self) -> None:
        umbrella = (MODULE_ROOT / "src" / "cae_logger.h").read_text(encoding="utf-8")

        removed_macros = [
            "CAE_LOG_TRACE",
            "CAE_LOG_DEBUG",
            "CAE_LOG_INFO",
            "CAE_LOG_WARN",
            "CAE_LOG_ERROR",
            "CAE_LOG_CRITICAL",
            "CAE_LOG_SCOPE_TRACE",
            "CAE_LOG_SCOPE_DEBUG",
            "CAE_LOG_SCOPE_INFO",
            "CAE_LOG_SCOPE_WARN",
            "CAE_LOG_SCOPE_ERROR",
            "CAE_LOG_SCOPE_CRITICAL",
        ]

        self.assertIn("#define CAE_LOG(level)", umbrella)
        self.assertIn("#define CAE_LOG_SCOPE(level)", umbrella)
        self.assertNotIn("#define CAE_LOG_SCOPE(level, module, ...)", umbrella)
        for macro_name in removed_macros:
            self.assertNotRegex(umbrella, rf"#define\s+{macro_name}\s*\(")

    def test_scoped_timer_exposes_chain_configuration_api(self) -> None:
        scoped_timer = (MODULE_ROOT / "src" / "cae_scoped_timer.h").read_text(encoding="utf-8")

        self.assertIn("explicit ScopedTimer(Level theLevel);", scoped_timer)
        self.assertIn("ScopedTimer& module(const char* theModule);", scoped_timer)
        self.assertIn("ScopedTimer& message(fmt::format_string<Args...> theFormat, Args&&... theArgs)", scoped_timer)

    def test_schema_header_is_installed_by_cmake(self) -> None:
        schema_header = MODULE_ROOT / "src" / "cae_event_schema.h"
        cmake = (MODULE_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

        self.assertTrue(schema_header.is_file())
        self.assertIn("src/cae_event_schema.h", cmake)
        self.assertIn("src/cae_log_builder.h", cmake)
        self.assertIn("src/cae_logger_types.h", cmake)
        self.assertIn("src/cae_scoped_timer.h", cmake)
        self.assertIn("src/cae_task_scope.h", cmake)
        self.assertIn("CAE_LOGGER_ENABLE_STACKTRACE", cmake)

    def test_cmake_consumes_spdlog_as_headers_or_package_not_source(self) -> None:
        root_cmake = (MODULE_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        package_config = (MODULE_ROOT / "cmake" / "cae_loggerConfig.cmake.in").read_text(encoding="utf-8")
        goaccess_cmake = (GOACCESS_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

        self.assertIn("cmake_minimum_required(VERSION 2.8.12)", root_cmake)
        self.assertNotIn('add_subdirectory("${CAE_BUNDLED_SPDLOG_DIR}"', root_cmake)
        self.assertNotIn("CAE_LOGGER_USE_BUNDLED_SPDLOG", root_cmake)
        self.assertNotIn("CAE_BUNDLED_SPDLOG", root_cmake)
        self.assertNotIn("thirdparty/spdlog", root_cmake)
        self.assertIn('set(CAE_LOGGER_SPDLOG_MODE "HEADER_ONLY"', root_cmake)
        self.assertIn('set(CAE_LOGGER_SPDLOG_INCLUDE_DIR "" CACHE PATH', root_cmake)
        self.assertIn('$<BUILD_INTERFACE:${CAE_LOGGER_SPDLOG_INCLUDE_DIR}>', root_cmake)
        self.assertNotIn("INTERFACE IMPORTED", root_cmake)
        self.assertIn('find_package(spdlog REQUIRED CONFIG PATHS "${CAE_LOGGER_SPDLOG_PACKAGE_DIR}" NO_DEFAULT_PATH)', root_cmake)
        self.assertIn('set(_CAE_LOGGER_SPDLOG_TARGET "@CAE_SPDLOG_TARGET@")', package_config)
        self.assertIn("find_package(spdlog REQUIRED CONFIG)", package_config)
        self.assertNotIn("add_library(spdlog::spdlog_header_only INTERFACE IMPORTED)", package_config)
        self.assertNotIn("NO_DEFAULT_PATH", package_config)
        self.assertIn('option(GOACCESS_ALLOW_SYSTEM_DEPS "Allow dependencies outside this repository', goaccess_cmake)
        self.assertIn('option(ENABLE_DEBUG      "Create a debug build" ${_GOACCESS_ENABLE_DEBUG_DEFAULT})', goaccess_cmake)
        self.assertIn('option(WITH_ZLIB         "Build with zlib support for reading gzipped logs" ${_GOACCESS_WITH_ZLIB_DEFAULT})', goaccess_cmake)
        self.assertIn('option(GOACCESS_ENABLE_ASAN "Build with AddressSanitizer when ENABLE_DEBUG is ON" OFF)', goaccess_cmake)
        self.assertIn("target_link_options(goaccess PRIVATE -fsanitize=address)", goaccess_cmake)
        self.assertIn('message(FATAL_ERROR "System zlib packages are not allowed', goaccess_cmake)
        self.assertIn('message(FATAL_ERROR "System curses/ncurses packages are not allowed', goaccess_cmake)

    def test_mingw_gcc_scope_removes_msvc_specific_code(self) -> None:
        source_paths = [
            WORKSPACE_ROOT / "README.md",
            MODULE_ROOT / "CMakeLists.txt",
            MODULE_ROOT / "build.cmd",
            MODULE_ROOT / "build.sh",
            MODULE_ROOT / "src" / "cae_log_builder.h",
            MODULE_ROOT / "src" / "cae_logger_types.h",
            MODULE_ROOT / "src" / "cae_scoped_timer.h",
            MODULE_ROOT / "src" / "cae_task_scope.h",
            TEST_ROOT / "build.cmd",
            TEST_ROOT / "build.sh",
            TEST_ROOT / "tools" / "common" / "cae_env.py",
            TEST_ROOT / "tools" / "tests" / "test_cae_env.py",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
        umbrella = (MODULE_ROOT / "src" / "cae_logger.h").read_text(encoding="utf-8")

        self.assertNotIn("MSVC", combined)
        self.assertNotIn("Visual Studio", combined)
        self.assertNotIn("_MSC_VER", combined)
        self.assertNotIn("generator-platform", combined)
        self.assertNotIn("generator-toolset", combined)
        self.assertNotIn("thirdparty/spdlog", combined.replace("\\", "/"))
        self.assertNotIn("std::optional", umbrella)

    def test_refactor_splits_each_logger_class_into_dedicated_header_and_source(self) -> None:
        expected_files = [
            "src/cae_console_printer.cpp",
            "src/cae_console_printer.h",
            "src/cae_jsonl_analysis_printer.cpp",
            "src/cae_jsonl_analysis_printer.h",
            "src/cae_log_builder.cpp",
            "src/cae_log_builder.h",
            "src/cae_logger_core.cpp",
            "src/cae_logger_core.h",
            "src/cae_printer.cpp",
            "src/cae_printer.h",
            "src/cae_scoped_timer.cpp",
            "src/cae_scoped_timer.h",
            "src/cae_task_scope.cpp",
            "src/cae_task_scope.h",
            "src/cae_text_file_printer.cpp",
            "src/cae_text_file_printer.h",
        ]

        for relative_path in expected_files:
            self.assertTrue((MODULE_ROOT / relative_path).is_file(), relative_path)

    def test_runtime_config_declares_phase1_knobs_and_schema_registry(self) -> None:
        config = (MODULE_ROOT / "config" / "cae_logger_config.ini").read_text(encoding="utf-8")
        schema = TEST_ROOT / "config" / "cae_event_schema_v1.json"

        self.assertIn("async_overflow_policy", config)
        self.assertIn("call_chain_sample_rate", config)
        self.assertIn("job_id", config)
        self.assertTrue(schema.is_file())

    def test_python_schema_registry_uses_repo_config_path(self) -> None:
        self.assertEqual(SCHEMA_REGISTRY_PATH, TEST_ROOT / "config" / "cae_event_schema_v1.json")
        self.assertTrue(SCHEMA_REGISTRY_PATH.is_file())

    def test_runtime_config_declares_phase3_resilience_knobs(self) -> None:
        header = (MODULE_ROOT / "src" / "cae_logger_types.h").read_text(encoding="utf-8")
        implementation = "\n".join(
            (
                (MODULE_ROOT / "src" / "cae_logger_detail.cpp").read_text(encoding="utf-8"),
                (MODULE_ROOT / "src" / "cae_logger_core.cpp").read_text(encoding="utf-8"),
                (MODULE_ROOT / "src" / "cae_jsonl_analysis_printer.cpp").read_text(encoding="utf-8"),
            )
        )
        config = (MODULE_ROOT / "config" / "cae_logger_config.ini").read_text(encoding="utf-8")

        self.assertIn("analysis_log_max_bytes = 128 * 1024 * 1024", header)
        self.assertIn("analysis_log_retention_files = 0", header)
        self.assertIn("logger_health_interval_events = 1000", header)
        self.assertIn("enable_lossy_drop_policy = false", header)
        self.assertIn("lossy_drop_below_level = Level::Trace", header)
        self.assertIn('aKey == "analysis_log_max_bytes"', implementation)
        self.assertIn('aKey == "analysis_log_retention_files"', implementation)
        self.assertIn('aKey == "logger_health_interval_events"', implementation)
        self.assertIn('aKey == "enable_lossy_drop_policy"', implementation)
        self.assertIn('aKey == "lossy_drop_below_level"', implementation)
        self.assertIn("health_snapshot", implementation)
        self.assertIn("analysis_segments_created", implementation)
        self.assertIn("records_dropped", implementation)
        self.assertIn("analysis_log_max_bytes = 134217728", config)
        self.assertIn("analysis_log_retention_files = 0", config)
        self.assertIn("logger_health_interval_events = 1000", config)
        self.assertIn("enable_lossy_drop_policy = false", config)
        self.assertIn("lossy_drop_below_level = trace", config)

    def test_rotation_logic_scans_existing_segments_and_uses_next_unused_index(self) -> None:
        implementation = (
            MODULE_ROOT / "src" / "cae_jsonl_analysis_printer.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("matching_segments_unlocked", implementation)
        self.assertIn("select_initial_segment_index_unlocked", implementation)
        self.assertIn("next_unused_segment_index_unlocked", implementation)
        self.assertIn("remove_matching_segments_unlocked", implementation)
        self.assertIn("open_segment_unlocked(select_initial_segment_index_unlocked(), false);", implementation)
        self.assertIn("next_unused_segment_index_unlocked(mySegmentIndex + 1)", implementation)

    def test_goaccess_profile_skips_additive_schema_v1_fields(self) -> None:
        profile = (TEST_ROOT / "config" / "cae_goaccess.conf").read_text(encoding="utf-8")

        self.assertIn('"schema_version":"%^"', profile)
        self.assertIn('"timestamp_epoch_us":%^', profile)
        self.assertIn('"monotonic_us":%^', profile)
        self.assertIn('"event_type":"%^"', profile)
        self.assertIn('"phase":"%^"', profile)
        self.assertIn('"domain":"%^"', profile)
        self.assertIn('"entity_type":"%^"', profile)
        self.assertIn('"entity_name":"%^"', profile)
        self.assertIn('"job_id":"%^"', profile)
        self.assertIn('"date":"%d"', profile)
        self.assertIn('"time":"%t"', profile)
        self.assertIn('"component":"%v"', profile)

    def test_samples_use_representative_schema_v1_semantics(self) -> None:
        main_sample = (TEST_ROOT / "sample" / "main.cpp").read_text(encoding="utf-8")
        post_sample = (TEST_ROOT / "sample" / "cae_postprocess_demo.cpp").read_text(encoding="utf-8")

        combined = main_sample + post_sample
        self.assertIn("cae::set_job_id", combined)
        self.assertIn(".event_type(cae::EventType::Geometry)", main_sample)
        self.assertIn(".event_type(cae::EventType::Mesh)", main_sample)
        self.assertIn(".event_type(cae::EventType::Solve)", main_sample)
        self.assertIn(".event_type(cae::EventType::PostProcess)", combined)
        self.assertIn(".domain(cae::Domain::CFD)", combined)
        self.assertIn(".phase(cae::EventPhase::Progress)", combined)
        self.assertIn("{\n        cae::TaskScope workflow_scope", main_sample)
        self.assertIn("    }\n    cae::shutdown();", main_sample)


if __name__ == "__main__":
    unittest.main()
