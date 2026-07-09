foreach(required_var
    MANIFEST_PATH
    APP_EXE
    APP_BUILD_DIR
    APP_CONFIG_DIR
    CAE_LOGGER_DIR
    GOACCESS_EXE
    GOACCESS_BUILD_DIR
    GOACCESS_SOURCE_DIR
    LOGS_DIR
    REPORTS_DIR
    PROFILE_CONFIG
    TEST_CONFIG
)
    if(NOT DEFINED ${required_var} OR "${${required_var}}" STREQUAL "")
        message(FATAL_ERROR "${required_var} is required")
    endif()
endforeach()

foreach(path_var
    MANIFEST_PATH
    APP_EXE
    APP_BUILD_DIR
    APP_CONFIG_DIR
    CAE_LOGGER_DIR
    GOACCESS_EXE
    GOACCESS_BUILD_DIR
    GOACCESS_SOURCE_DIR
    LOGS_DIR
    REPORTS_DIR
    PROFILE_CONFIG
)
    get_filename_component(${path_var}_ABS "${${path_var}}" ABSOLUTE)
    file(TO_CMAKE_PATH "${${path_var}_ABS}" ${path_var}_JSON)
endforeach()

get_filename_component(MANIFEST_DIR "${MANIFEST_PATH_ABS}" DIRECTORY)
file(MAKE_DIRECTORY "${MANIFEST_DIR}" "${LOGS_DIR_ABS}" "${REPORTS_DIR_ABS}")

file(WRITE "${MANIFEST_PATH_ABS}" "{\n")
file(APPEND "${MANIFEST_PATH_ABS}" "  \"app\": {\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"build_dir\": \"${APP_BUILD_DIR_JSON}\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"cae_logger_dir\": \"${CAE_LOGGER_DIR_JSON}\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"config\": \"${TEST_CONFIG}\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"config_dir\": \"${APP_CONFIG_DIR_JSON}\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"exe\": \"${APP_EXE_JSON}\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"spdlog_dir\": null\n")
file(APPEND "${MANIFEST_PATH_ABS}" "  },\n")
file(APPEND "${MANIFEST_PATH_ABS}" "  \"goaccess\": {\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"build_dir\": \"${GOACCESS_BUILD_DIR_JSON}\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"cmake_cache\": \"${GOACCESS_BUILD_DIR_JSON}/CMakeCache.txt\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"config_h\": \"${GOACCESS_BUILD_DIR_JSON}/config.h\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"exe\": \"${GOACCESS_EXE_JSON}\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"source_dir\": \"${GOACCESS_SOURCE_DIR_JSON}\"\n")
file(APPEND "${MANIFEST_PATH_ABS}" "  },\n")
file(APPEND "${MANIFEST_PATH_ABS}" "  \"logs_dir\": \"${LOGS_DIR_JSON}\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "  \"main\": {\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"package_dir\": \"${CAE_LOGGER_DIR_JSON}\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"config\": \"${TEST_CONFIG}\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "    \"spdlog_dir\": null\n")
file(APPEND "${MANIFEST_PATH_ABS}" "  },\n")
file(APPEND "${MANIFEST_PATH_ABS}" "  \"profile_config\": \"${PROFILE_CONFIG_JSON}\",\n")
file(APPEND "${MANIFEST_PATH_ABS}" "  \"reports_dir\": \"${REPORTS_DIR_JSON}\"\n")
file(APPEND "${MANIFEST_PATH_ABS}" "}\n")

message(STATUS "Wrote CAE manifest: ${MANIFEST_PATH_ABS}")
