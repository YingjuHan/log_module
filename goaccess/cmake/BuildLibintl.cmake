# BuildLibintl.cmake — Create libintl interface from MinGW runtime DLL
#
# The GNU gettext libintl source requires gnulib (30+ modules) which is not
# bundled in the Savannah tarball.  On MinGW-w64 a working libintl-8.dll is
# provided by the runtime package.  This module generates the header from
# source (via configure_file) and creates the import library from the DLL.
#
# Prerequisites:
#   GETTEXT_SRC_DIR – path to gettext source tree root (e.g. ../3rdparty/gettext)
#
# Provides:
#   - Generated libintl.h in build include path
#   - libintl.dll.a import library linked to goaccess
#   - libintl-8.dll copied to output dir (runtime dependency)

if(NOT GETTEXT_SRC_DIR)
    message(FATAL_ERROR "GETTEXT_SRC_DIR must be set to the gettext source tree root")
endif()

set(INTL_SRC_DIR "${GETTEXT_SRC_DIR}/gettext-runtime/intl")

# ------------------------------------------------------------------
# 1. Find the MinGW runtime libintl-8.dll
# ------------------------------------------------------------------
find_file(LIBINTL_DLL
    NAMES libintl-8.dll
    PATHS
        "$ENV{DIR}/bin"
        "D:/mingw64/bin"
        "C:/msys64/mingw64/bin"
        "C:/msys64/mingw32/bin"
        "C:/mingw-w64/x86_64-8.1.0-posix-seh-rt_v6-rev0/mingw64/bin"
    NO_DEFAULT_PATH
)

if(NOT LIBINTL_DLL)
    message(FATAL_ERROR
        "libintl-8.dll not found.\n"
        "Install MinGW-w64 with gettext runtime (libintl-8.dll).\n"
        "Expected at D:/mingw64/bin/libintl-8.dll or similar."
    )
endif()

get_filename_component(LIBINTL_DLL_DIR "${LIBINTL_DLL}" DIRECTORY)

message(STATUS "libintl: using ${LIBINTL_DLL}")

# ------------------------------------------------------------------
# 2. Create import library libintl.dll.a from the DLL at configure time
#    (gendef/dlltool run once when CMake configures; the DLL exports
#    are stable so this doesn't need rebuild-time tracking)
# ------------------------------------------------------------------
set(LIBINTL_IMPLIB "${CMAKE_CURRENT_BINARY_DIR}/libintl.dll.a")

find_program(GENDEF_PROGRAM gendef)
find_program(DLLTOOL_PROGRAM dlltool)

if(NOT GENDEF_PROGRAM)
    message(FATAL_ERROR "gendef not found — required to create libintl import library")
endif()
if(NOT DLLTOOL_PROGRAM)
    message(FATAL_ERROR "dlltool not found — required to create libintl import library")
endif()

if(NOT EXISTS "${LIBINTL_IMPLIB}")
    set(LIBINTL_DLL_DEF "${CMAKE_CURRENT_BINARY_DIR}/libintl-8.def")
    message(STATUS "libintl: generating ${LIBINTL_DLL_DEF} ...")
    execute_process(
        COMMAND "${GENDEF_PROGRAM}" "${LIBINTL_DLL}"
        WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
        OUTPUT_VARIABLE GENDEF_OUT
        ERROR_VARIABLE  GENDEF_ERR
        RESULT_VARIABLE GENDEF_RES
    )
    if(NOT GENDEF_RES EQUAL 0)
        message(FATAL_ERROR "gendef failed: ${GENDEF_ERR}")
    endif()
    if(NOT EXISTS "${LIBINTL_DLL_DEF}")
        message(FATAL_ERROR "gendef did not produce ${LIBINTL_DLL_DEF}")
    endif()
    message(STATUS "libintl: creating ${LIBINTL_IMPLIB} ...")
    execute_process(
        COMMAND "${DLLTOOL_PROGRAM}"
            --input-def "${LIBINTL_DLL_DEF}"
            --output-lib "${LIBINTL_IMPLIB}"
            --dllname "libintl-8.dll"
        WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
        RESULT_VARIABLE DLLTOOL_RES
    )
    if(NOT DLLTOOL_RES EQUAL 0)
        message(FATAL_ERROR "dlltool failed with status ${DLLTOOL_RES}")
    endif()
    message(STATUS "libintl: ${LIBINTL_IMPLIB} created (${LIBINTL_IMPLIB_SIZE} bytes)")
else()
    message(STATUS "libintl: using existing ${LIBINTL_IMPLIB}")
endif()

# ------------------------------------------------------------------
# 3. Generate libintl.h from the source template
#    (provides the correct public API via configure_file)
# ------------------------------------------------------------------
set(HAVE_POSIX_PRINTF 0)
set(HAVE_ASPRINTF     0)
set(HAVE_SNPRINTF     1)
set(HAVE_WPRINTF      0)
set(HAVE_NEWLOCALE    0)
set(ENHANCE_LOCALE_FUNCS 0)
set(HAVE_VISIBILITY   0)

file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/intl")

configure_file(
    "${INTL_SRC_DIR}/libgnuintl.in.h"
    "${CMAKE_CURRENT_BINARY_DIR}/intl/libintl.h"
    @ONLY
)

# ------------------------------------------------------------------
# 4. Interface target for linking
# ------------------------------------------------------------------
add_library(libintl INTERFACE)
target_include_directories(libintl INTERFACE
    "${CMAKE_CURRENT_BINARY_DIR}/intl"
)
target_link_libraries(libintl INTERFACE
    "${LIBINTL_IMPLIB}"
)

# Mirror the configure.ac contract once the MinGW gettext runtime is active.
set(HAVE_LIBINTL 1)
set(HAVE_GETTEXT 1)
set(HAVE_DCGETTEXT 1)
if(NOT HAVE_ICONV)
    set(HAVE_ICONV 1)
endif()

# Copy DLL to output directory for runtime loading
add_custom_command(TARGET goaccess POST_BUILD
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
        "${LIBINTL_DLL}"
        "$<TARGET_FILE_DIR:goaccess>"
    COMMENT "Copying libintl-8.dll to output dir"
)
