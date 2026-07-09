cmake_minimum_required(VERSION 2.8.12)
if(POLICY CMP0048)
    cmake_policy(SET CMP0048 NEW)
endif()
project(cae_logger CXX)

set(PROJECT_VERSION 1.0.0)
set(PROJECT_VERSION_MAJOR 1)
set(PROJECT_VERSION_MINOR 0)
set(PROJECT_VERSION_PATCH 0)

if(CMAKE_VERSION VERSION_LESS "3.1")
    set(CAE_LOGGER_NEEDS_CXX11_FLAG ON)
else()
    set(CMAKE_CXX_STANDARD 11)
    set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()

option(CAE_LOGGER_SYMBOLIC_STACKTRACE "Build with flags that improve boost::stacktrace symbol names" ON)
option(CAE_LOGGER_ENABLE_STACKTRACE "Enable boost::stacktrace call chain capture" ON)
option(CAE_LOGGER_BUILD_DOCS "Build Doxygen HTML documentation for cae_logger" ON)
option(CAE_LOGGER_INSTALL_DOCS "Install generated Doxygen HTML documentation" ON)
option(CAE_LOGGER_INSTALL_TEST_PROJECT "Install the standalone cae_logger test source project" ON)
set(CAE_LOGGER_SPDLOG_MODE "HEADER_ONLY" CACHE STRING "How cae_logger consumes spdlog: HEADER_ONLY or PACKAGE")
set_property(CACHE CAE_LOGGER_SPDLOG_MODE PROPERTY STRINGS HEADER_ONLY PACKAGE)
set(CAE_LOGGER_SPDLOG_INCLUDE_DIR "" CACHE PATH "Directory containing spdlog headers when CAE_LOGGER_SPDLOG_MODE=HEADER_ONLY")
set(CAE_LOGGER_SPDLOG_PACKAGE_DIR "" CACHE PATH "Directory containing spdlogConfig.cmake when CAE_LOGGER_SPDLOG_MODE=PACKAGE")
option(CAE_LOGGER_INSTALL_SPDLOG_HEADERS "Install spdlog headers when CAE_LOGGER_SPDLOG_MODE=HEADER_ONLY" ON)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
include(GenerateExportHeader)

set(CAE_THIRDPARTY_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/thirdparty")

string(TOUPPER "${CAE_LOGGER_SPDLOG_MODE}" CAE_LOGGER_SPDLOG_MODE_UPPER)

if(CAE_LOGGER_SPDLOG_MODE_UPPER STREQUAL "HEADER_ONLY")
    if(NOT CAE_LOGGER_SPDLOG_INCLUDE_DIR)
        message(FATAL_ERROR "CAE_LOGGER_SPDLOG_INCLUDE_DIR is required when CAE_LOGGER_SPDLOG_MODE=HEADER_ONLY.")
    endif()
    get_filename_component(CAE_LOGGER_SPDLOG_INCLUDE_DIR "${CAE_LOGGER_SPDLOG_INCLUDE_DIR}" ABSOLUTE)
    if(NOT EXISTS "${CAE_LOGGER_SPDLOG_INCLUDE_DIR}/spdlog/spdlog.h")
        message(FATAL_ERROR "spdlog headers are missing: ${CAE_LOGGER_SPDLOG_INCLUDE_DIR}")
    endif()

    set(CAE_LOGGER_USE_HEADER_ONLY_SPDLOG ON)
elseif(CAE_LOGGER_SPDLOG_MODE_UPPER STREQUAL "PACKAGE")
    if(NOT CAE_LOGGER_SPDLOG_PACKAGE_DIR)
        message(FATAL_ERROR "CAE_LOGGER_SPDLOG_PACKAGE_DIR is required when CAE_LOGGER_SPDLOG_MODE=PACKAGE.")
    endif()

    find_package(spdlog REQUIRED CONFIG PATHS "${CAE_LOGGER_SPDLOG_PACKAGE_DIR}" NO_DEFAULT_PATH)
    if(TARGET spdlog::spdlog_header_only)
        set(CAE_SPDLOG_TARGET spdlog::spdlog_header_only)
    elseif(TARGET spdlog::spdlog)
        set(CAE_SPDLOG_TARGET spdlog::spdlog)
    else()
        message(FATAL_ERROR "The spdlog package at ${CAE_LOGGER_SPDLOG_PACKAGE_DIR} did not define spdlog::spdlog or spdlog::spdlog_header_only.")
    endif()
else()
    message(FATAL_ERROR "Unsupported CAE_LOGGER_SPDLOG_MODE: ${CAE_LOGGER_SPDLOG_MODE}. Use HEADER_ONLY or PACKAGE.")
endif()

set(CAE_LOCAL_BOOST_ROOT "${CAE_THIRDPARTY_ROOT}/boost_1_68_0")
set(CAE_LOGGER_STACKTRACE_AVAILABLE OFF)
if(CAE_LOGGER_ENABLE_STACKTRACE AND EXISTS "${CAE_LOCAL_BOOST_ROOT}/boost/stacktrace.hpp")
    set(CAE_LOGGER_STACKTRACE_AVAILABLE ON)
elseif(CAE_LOGGER_ENABLE_STACKTRACE)
    message(WARNING "Boost stacktrace headers not found under ${CAE_LOCAL_BOOST_ROOT}; call-chain capture will be disabled.")
endif()

add_library(cae_logger SHARED
    src/cae_console_printer.cpp
    src/cae_console_printer.h
    src/cae_compat.h
    src/cae_filesystem.h
    src/cae_logger.cpp
    src/cae_log_builder.cpp
    src/cae_log_builder.h
    src/cae_logger_core.cpp
    src/cae_logger_core.h
    src/cae_logger_detail.cpp
    src/cae_logger_detail.h
    src/cae_logger.h
    src/cae_logger_types.h
    src/cae_jsonl_analysis_printer.cpp
    src/cae_jsonl_analysis_printer.h
    src/cae_printer.cpp
    src/cae_printer.h
    src/cae_scoped_timer.cpp
    src/cae_scoped_timer.h
    src/cae_task_scope.cpp
    src/cae_task_scope.h
    src/cae_event_schema.h
    src/cae_text_file_printer.cpp
    src/cae_text_file_printer.h
)

generate_export_header(cae_logger
    EXPORT_FILE_NAME "${CMAKE_CURRENT_BINARY_DIR}/generated/cae_logger_export.h"
)

target_include_directories(cae_logger
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src>
        $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}/generated>
        $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
    PRIVATE
        "${CAE_LOCAL_BOOST_ROOT}"
)

if(CAE_LOGGER_USE_HEADER_ONLY_SPDLOG)
    target_include_directories(cae_logger
        PUBLIC
            $<BUILD_INTERFACE:${CAE_LOGGER_SPDLOG_INCLUDE_DIR}>
    )
endif()

if(CAE_SPDLOG_TARGET)
    target_link_libraries(cae_logger
        PUBLIC
            ${CAE_SPDLOG_TARGET}
    )
endif()

if(CAE_LOGGER_NEEDS_CXX11_FLAG)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(cae_logger PRIVATE -std=c++11)
    endif()
endif()

if(UNIX AND NOT APPLE)
    target_compile_definitions(cae_logger PRIVATE _POSIX_C_SOURCE=200809L)
endif()

if(CAE_LOGGER_STACKTRACE_AVAILABLE)
    target_compile_definitions(cae_logger PRIVATE CAE_LOGGER_ENABLE_STACKTRACE=1)
else()
    target_compile_definitions(cae_logger PRIVATE CAE_LOGGER_ENABLE_STACKTRACE=0)
endif()

if(CAE_LOGGER_STACKTRACE_AVAILABLE AND CAE_LOGGER_SYMBOLIC_STACKTRACE AND (CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang"))
    target_compile_options(cae_logger PRIVATE -g -fno-omit-frame-pointer)
endif()

set_target_properties(cae_logger PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION ${PROJECT_VERSION_MAJOR}
    EXPORT_NAME cae_logger
)

file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/logs")

write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/cae_loggerConfigVersion.cmake"
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

configure_package_config_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/cae_loggerConfig.cmake.in"
    "${CMAKE_CURRENT_BINARY_DIR}/cae_loggerConfig.cmake"
    INSTALL_DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/cae_logger"
)

set(CAE_LOGGER_DOXYGEN_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}/docs")
set(CAE_LOGGER_DOXYGEN_HTML_DIR "${CAE_LOGGER_DOXYGEN_OUTPUT_DIR}/html")
set(CAE_LOGGER_DOXYGEN_FILE "${CMAKE_CURRENT_BINARY_DIR}/Doxyfile")

if(CAE_LOGGER_BUILD_DOCS OR CAE_LOGGER_INSTALL_DOCS)
    find_package(Doxygen REQUIRED)
    configure_file(
        "${CMAKE_CURRENT_SOURCE_DIR}/cmake/Doxyfile.in"
        "${CAE_LOGGER_DOXYGEN_FILE}"
        @ONLY
    )

    add_custom_target(cae_logger_docs ALL
        COMMAND "${DOXYGEN_EXECUTABLE}" "${CAE_LOGGER_DOXYGEN_FILE}"
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        COMMENT "Generating cae_logger Doxygen HTML documentation"
        VERBATIM
    )
endif()

install(
    TARGETS cae_logger
    EXPORT cae_loggerTargets
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)

file(GLOB CAE_LOGGER_PUBLIC_HEADERS
    "${CMAKE_CURRENT_SOURCE_DIR}/src/cae_*.h"
)
list(SORT CAE_LOGGER_PUBLIC_HEADERS)
list(APPEND CAE_LOGGER_PUBLIC_HEADERS
    "${CMAKE_CURRENT_BINARY_DIR}/generated/cae_logger_export.h"
)

install(
    FILES ${CAE_LOGGER_PUBLIC_HEADERS}
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

if(CAE_LOGGER_SPDLOG_MODE_UPPER STREQUAL "HEADER_ONLY" AND CAE_LOGGER_INSTALL_SPDLOG_HEADERS)
    install(
        DIRECTORY "${CAE_LOGGER_SPDLOG_INCLUDE_DIR}/spdlog"
        DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
    )
endif()

install(
    FILES "${CMAKE_CURRENT_SOURCE_DIR}/config/cae_logger_config.ini"
    DESTINATION ${CMAKE_INSTALL_BINDIR}
)

install(
    EXPORT cae_loggerTargets
    FILE cae_loggerTargets.cmake
    NAMESPACE cae_logger::
    DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/cae_logger"
)

install(
    FILES
        "${CMAKE_CURRENT_BINARY_DIR}/cae_loggerConfig.cmake"
        "${CMAKE_CURRENT_BINARY_DIR}/cae_loggerConfigVersion.cmake"
    DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/cae_logger"
)

if(CAE_LOGGER_INSTALL_DOCS)
    install(
        DIRECTORY "${CAE_LOGGER_DOXYGEN_HTML_DIR}/"
        DESTINATION "${CMAKE_INSTALL_DOCDIR}/html"
    )
endif()

if(CAE_LOGGER_INSTALL_TEST_PROJECT)
    get_filename_component(CAE_LOGGER_WORKSPACE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
    set(CAE_LOGGER_TEST_PROJECT_DIR "${CAE_LOGGER_WORKSPACE_ROOT}/test")

    install(
        FILES
            "${CAE_LOGGER_TEST_PROJECT_DIR}/CMakeLists.txt"
            "${CAE_LOGGER_TEST_PROJECT_DIR}/build.cmd"
            "${CAE_LOGGER_TEST_PROJECT_DIR}/build.sh"
        DESTINATION "${CMAKE_INSTALL_DATADIR}/cae_logger/test"
    )

    install(
        DIRECTORY
            "${CAE_LOGGER_TEST_PROJECT_DIR}/sample"
            "${CAE_LOGGER_TEST_PROJECT_DIR}/config"
            "${CAE_LOGGER_TEST_PROJECT_DIR}/cmake"
            "${CAE_LOGGER_TEST_PROJECT_DIR}/tools"
        DESTINATION "${CMAKE_INSTALL_DATADIR}/cae_logger/test"
        PATTERN "build" EXCLUDE
        PATTERN "out" EXCLUDE
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
    )
endif()
