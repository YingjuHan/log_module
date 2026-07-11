#!/usr/bin/env bash
set -euxo pipefail

install -d "${PREFIX}/include" "${PREFIX}/lib/cmake/spdlog"
cp -R include/spdlog "${PREFIX}/include/"

cat > "${PREFIX}/lib/cmake/spdlog/spdlogConfig.cmake" <<'EOF'
include(CMakeFindDependencyMacro)
find_dependency(fmt 9.1.0 CONFIG)
if(UNIX)
  find_dependency(Threads)
endif()

get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)

if(NOT TARGET spdlog::spdlog_header_only)
  add_library(spdlog::spdlog_header_only INTERFACE IMPORTED)
  set_target_properties(spdlog::spdlog_header_only PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES "${PACKAGE_PREFIX_DIR}/include"
    INTERFACE_COMPILE_DEFINITIONS "SPDLOG_FMT_EXTERNAL"
    INTERFACE_LINK_LIBRARIES "fmt::fmt-header-only"
  )
  if(UNIX)
    set_property(TARGET spdlog::spdlog_header_only APPEND PROPERTY
      INTERFACE_LINK_LIBRARIES Threads::Threads)
  endif()
endif()
EOF

cat > "${PREFIX}/lib/cmake/spdlog/spdlogConfigVersion.cmake" <<'EOF'
set(PACKAGE_VERSION "1.11.0")
set(PACKAGE_VERSION_COMPATIBLE FALSE)
set(PACKAGE_VERSION_EXACT FALSE)

if("${PACKAGE_FIND_VERSION_MAJOR}" STREQUAL "1")
  if(NOT "${PACKAGE_FIND_VERSION}" VERSION_GREATER "${PACKAGE_VERSION}")
    set(PACKAGE_VERSION_COMPATIBLE TRUE)
    if("${PACKAGE_FIND_VERSION}" VERSION_EQUAL "${PACKAGE_VERSION}")
      set(PACKAGE_VERSION_EXACT TRUE)
    endif()
  endif()
endif()
EOF
