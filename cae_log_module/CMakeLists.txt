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

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
include(GenerateExportHeader)

find_package(fmt 9.1.0 REQUIRED CONFIG)
if(NOT TARGET fmt::fmt-header-only)
    message(FATAL_ERROR "cae_logger requires the external header-only target fmt::fmt-header-only.")
endif()

find_package(spdlog 1.11.0 REQUIRED CONFIG)
if(NOT TARGET spdlog::spdlog_header_only)
    message(FATAL_ERROR "cae_logger requires the external header-only target spdlog::spdlog_header_only.")
endif()

get_target_property(CAE_LOGGER_SPDLOG_COMPILE_DEFINITIONS
    spdlog::spdlog_header_only INTERFACE_COMPILE_DEFINITIONS)
list(FIND CAE_LOGGER_SPDLOG_COMPILE_DEFINITIONS
    "SPDLOG_FMT_EXTERNAL" CAE_LOGGER_SPDLOG_FMT_EXTERNAL_INDEX)
if(CAE_LOGGER_SPDLOG_FMT_EXTERNAL_INDEX EQUAL -1)
    message(FATAL_ERROR "spdlog::spdlog_header_only must enable SPDLOG_FMT_EXTERNAL.")
endif()

get_target_property(CAE_LOGGER_SPDLOG_LINK_LIBRARIES
    spdlog::spdlog_header_only INTERFACE_LINK_LIBRARIES)
list(FIND CAE_LOGGER_SPDLOG_LINK_LIBRARIES
    "fmt::fmt-header-only" CAE_LOGGER_SPDLOG_FMT_TARGET_INDEX)
if(CAE_LOGGER_SPDLOG_FMT_TARGET_INDEX EQUAL -1)
    message(FATAL_ERROR "spdlog::spdlog_header_only must link fmt::fmt-header-only.")
endif()

set(CAE_LOGGER_STACKTRACE_AVAILABLE OFF)
if(CAE_LOGGER_ENABLE_STACKTRACE)
    # Use FindBoost's module mode so configured builds always use the external
    # Boost installation selected by the toolchain, never the vendored source.
    set(Boost_NO_BOOST_CMAKE ON)
    if(WIN32)
        set(CAE_LOGGER_BOOST_STACKTRACE_COMPONENT stacktrace_windbg)
    else()
        set(CAE_LOGGER_BOOST_STACKTRACE_COMPONENT stacktrace_basic)
    endif()

    find_package(Boost 1.68.0 REQUIRED COMPONENTS ${CAE_LOGGER_BOOST_STACKTRACE_COMPONENT})

    set(CAE_LOGGER_BOOST_STACKTRACE_LINK "")
    if(TARGET Boost::${CAE_LOGGER_BOOST_STACKTRACE_COMPONENT})
        set(CAE_LOGGER_BOOST_STACKTRACE_LINK Boost::${CAE_LOGGER_BOOST_STACKTRACE_COMPONENT})
    else()
        string(TOUPPER "${CAE_LOGGER_BOOST_STACKTRACE_COMPONENT}" CAE_LOGGER_BOOST_STACKTRACE_COMPONENT_UPPER)
        foreach(CAE_LOGGER_BOOST_STACKTRACE_LIBRARY_VARIABLE
                "Boost_${CAE_LOGGER_BOOST_STACKTRACE_COMPONENT}_LIBRARY"
                "Boost_${CAE_LOGGER_BOOST_STACKTRACE_COMPONENT_UPPER}_LIBRARY")
            if(DEFINED ${CAE_LOGGER_BOOST_STACKTRACE_LIBRARY_VARIABLE}
               AND NOT "${${CAE_LOGGER_BOOST_STACKTRACE_LIBRARY_VARIABLE}}" STREQUAL "")
                set(CAE_LOGGER_BOOST_STACKTRACE_LINK "${${CAE_LOGGER_BOOST_STACKTRACE_LIBRARY_VARIABLE}}")
                break()
            endif()
        endforeach()
    endif()

    if(NOT CAE_LOGGER_BOOST_STACKTRACE_LINK)
        message(FATAL_ERROR "FindBoost did not provide a library for Boost ${CAE_LOGGER_BOOST_STACKTRACE_COMPONENT}.")
    endif()

    set(CAE_LOGGER_STACKTRACE_AVAILABLE ON)
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
)

target_link_libraries(cae_logger
    PUBLIC
        fmt::fmt-header-only
        spdlog::spdlog_header_only
)

if(CAE_LOGGER_STACKTRACE_AVAILABLE)
    target_include_directories(cae_logger PRIVATE ${Boost_INCLUDE_DIRS})
    target_link_libraries(cae_logger PRIVATE ${CAE_LOGGER_BOOST_STACKTRACE_LINK})
    if(UNIX AND CMAKE_DL_LIBS)
        target_link_libraries(cae_logger PRIVATE ${CMAKE_DL_LIBS})
    endif()
endif()

if(CAE_LOGGER_NEEDS_CXX11_FLAG)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(cae_logger PRIVATE -std=c++11)
    endif()
endif()

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(cae_logger INTERFACE -Werror=unused-result)
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

set(CAE_LOGGER_PUBLIC_HEADERS
    "${CMAKE_CURRENT_SOURCE_DIR}/src/cae_compat.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/cae_event_schema.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/cae_log_builder.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/cae_logger.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/cae_logger_types.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/cae_scoped_timer.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/cae_task_scope.h"
    "${CMAKE_CURRENT_BINARY_DIR}/generated/cae_logger_export.h"
)

install(
    FILES ${CAE_LOGGER_PUBLIC_HEADERS}
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

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
        OPTIONAL
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
        PATTERN "tests" EXCLUDE
        PATTERN "__pycache__" EXCLUDE
        PATTERN "*.pyc" EXCLUDE
    )
endif()
