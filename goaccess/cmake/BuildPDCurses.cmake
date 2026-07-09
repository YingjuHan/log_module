# BuildPDCurses.cmake — Wrap PDCurses CMake build for inclusion
# in the GoAccess build tree.
#
# Prerequisites:
#   PDCURSES_SRC_DIR – path to PDCurses source tree root (e.g. ../3rdparty/PDCurses)

if(NOT PDCURSES_SRC_DIR)
    message(FATAL_ERROR "PDCURSES_SRC_DIR must be set to PDCurses source root")
endif()

# Guard: only add once
if(TARGET pdcurses)
    return()
endif()

add_subdirectory(
    "${PDCURSES_SRC_DIR}"
    "${CMAKE_CURRENT_BINARY_DIR}/PDCurses"
    EXCLUDE_FROM_ALL
)
