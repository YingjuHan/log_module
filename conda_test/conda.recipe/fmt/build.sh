#!/usr/bin/env bash
set -euxo pipefail

install -d "${PREFIX}/include" "${PREFIX}/lib/cmake/fmt"
cp -R include/fmt "${PREFIX}/include/"

cat > "${PREFIX}/lib/cmake/fmt/fmtConfig.cmake" <<'EOF'
get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)

if(NOT TARGET fmt::fmt-header-only)
  add_library(fmt::fmt-header-only INTERFACE IMPORTED)
  set_target_properties(fmt::fmt-header-only PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES "${PACKAGE_PREFIX_DIR}/include"
    INTERFACE_COMPILE_DEFINITIONS "FMT_HEADER_ONLY=1"
  )
endif()
EOF

cat > "${PREFIX}/lib/cmake/fmt/fmtConfigVersion.cmake" <<'EOF'
set(PACKAGE_VERSION "9.1.0")
set(PACKAGE_VERSION_COMPATIBLE FALSE)
set(PACKAGE_VERSION_EXACT FALSE)

if("${PACKAGE_FIND_VERSION_MAJOR}" STREQUAL "9")
  if(NOT "${PACKAGE_FIND_VERSION}" VERSION_GREATER "${PACKAGE_VERSION}")
    set(PACKAGE_VERSION_COMPATIBLE TRUE)
    if("${PACKAGE_FIND_VERSION}" VERSION_EQUAL "${PACKAGE_VERSION}")
      set(PACKAGE_VERSION_EXACT TRUE)
    endif()
  endif()
endif()
EOF
