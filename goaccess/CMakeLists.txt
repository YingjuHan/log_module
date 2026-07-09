cmake_minimum_required(VERSION 3.14)
project(goaccess VERSION 1.10.2 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

# ============================================================
# Options
# ============================================================
set(_GOACCESS_ENABLE_DEBUG_DEFAULT OFF)
if(CMAKE_BUILD_TYPE)
    string(TOUPPER "${CMAKE_BUILD_TYPE}" _GOACCESS_BUILD_TYPE_UPPER)
    if(_GOACCESS_BUILD_TYPE_UPPER STREQUAL "DEBUG")
        set(_GOACCESS_ENABLE_DEBUG_DEFAULT ON)
    endif()
endif()

set(_GOACCESS_THIRDPARTY_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/thirdparty")
set(_GOACCESS_GETTEXT_SRC_DIR_DEFAULT "")
set(_GOACCESS_ZLIB_SRC_DIR_DEFAULT "")
set(_GOACCESS_PDCURSES_SRC_DIR_DEFAULT "")
if(EXISTS "${_GOACCESS_THIRDPARTY_ROOT}/gettext")
    set(_GOACCESS_GETTEXT_SRC_DIR_DEFAULT "${_GOACCESS_THIRDPARTY_ROOT}/gettext")
endif()
if(EXISTS "${_GOACCESS_THIRDPARTY_ROOT}/zlib")
    set(_GOACCESS_ZLIB_SRC_DIR_DEFAULT "${_GOACCESS_THIRDPARTY_ROOT}/zlib")
endif()
if(EXISTS "${_GOACCESS_THIRDPARTY_ROOT}/PDCurses")
    set(_GOACCESS_PDCURSES_SRC_DIR_DEFAULT "${_GOACCESS_THIRDPARTY_ROOT}/PDCurses")
endif()

# Third-party source paths. The repository build keeps system dependencies disabled by default.
set(GETTEXT_SRC_DIR  "${_GOACCESS_GETTEXT_SRC_DIR_DEFAULT}" CACHE PATH "Path to GNU gettext source tree (e.g. thirdparty/gettext)")
set(ZLIB_SRC_DIR     "${_GOACCESS_ZLIB_SRC_DIR_DEFAULT}" CACHE PATH "Path to zlib source tree (e.g. thirdparty/zlib)")
set(PDCURSES_SRC_DIR "${_GOACCESS_PDCURSES_SRC_DIR_DEFAULT}" CACHE PATH "Path to PDCurses source tree (e.g. thirdparty/PDCurses)")

set(_GOACCESS_WITH_ZLIB_DEFAULT OFF)
if(DEFINED ZLIB_SRC_DIR AND NOT ZLIB_SRC_DIR STREQUAL "")
    set(_GOACCESS_WITH_ZLIB_DEFAULT ON)
endif()

option(ENABLE_DEBUG      "Create a debug build" ${_GOACCESS_ENABLE_DEBUG_DEFAULT})
option(WITH_SSL          "Build with OpenSSL/TLS support" OFF)
option(WITH_ZLIB         "Build with zlib support for reading gzipped logs" ${_GOACCESS_WITH_ZLIB_DEFAULT})
option(ENABLE_GEOIP      "Enable GeoIP (mmdb or legacy)" OFF)
option(ENABLE_NCURSES    "Build with ncurses terminal UI" ON)
option(ENABLE_NLS        "Enable Native Language Support (gettext)" OFF)
option(WITH_GETLINE      "Build using dynamic line buffer (POSIX getline)" OFF)
option(ENABLE_UTF8       "Enable ncursesw for wide character support" OFF)
option(GOACCESS_ENABLE_ASAN "Build with AddressSanitizer when ENABLE_DEBUG is ON" OFF)
option(GOACCESS_ALLOW_SYSTEM_DEPS "Allow dependencies outside this repository's 3rdparty directory" OFF)

function(goaccess_require_dependency_under option_name root_dir)
    if(NOT ${option_name})
        return()
    endif()

    get_filename_component(_dependency_path "${${option_name}}" ABSOLUTE)
    get_filename_component(_dependency_root "${root_dir}" ABSOLUTE)
    file(RELATIVE_PATH _dependency_rel "${_dependency_root}" "${_dependency_path}")
    if(_dependency_rel MATCHES "^\\.\\." OR IS_ABSOLUTE "${_dependency_rel}")
        message(FATAL_ERROR "${option_name} must point under ${_dependency_root}: ${_dependency_path}")
    endif()
endfunction()

if(NOT GOACCESS_ALLOW_SYSTEM_DEPS)
    goaccess_require_dependency_under(GETTEXT_SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/thirdparty")
    goaccess_require_dependency_under(ZLIB_SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/thirdparty")
    goaccess_require_dependency_under(PDCURSES_SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/thirdparty")
endif()

unset(_GOACCESS_ENABLE_DEBUG_DEFAULT)
unset(_GOACCESS_WITH_ZLIB_DEFAULT)
unset(_GOACCESS_BUILD_TYPE_UPPER)
unset(_GOACCESS_THIRDPARTY_ROOT)
unset(_GOACCESS_GETTEXT_SRC_DIR_DEFAULT)
unset(_GOACCESS_ZLIB_SRC_DIR_DEFAULT)
unset(_GOACCESS_PDCURSES_SRC_DIR_DEFAULT)

include(GNUInstallDirs)

# ============================================================
# Detect compiler and platform
# ============================================================
if(MSVC)
    add_compile_options(/utf-8 /W0)
    add_compile_definitions(_CRT_SECURE_NO_WARNINGS _CRT_NONSTDC_NO_WARNINGS)
    # MSVC doesn't have snprintf before VS2015
    if(MSVC_VERSION LESS 1900)
        add_compile_definitions(snprintf=_snprintf)
    endif()
endif()

if(MINGW OR CYGWIN)
    # MinGW provides most POSIX headers; just need some extras
    add_compile_definitions(_WIN32_WINNT=0x0601)
    # PDCurses/wincon.h MOUSE_MOVED conflict workaround
    # (applied to goaccess target only via target_compile_definitions below)
endif()

if(WIN32)
    add_compile_definitions(_WIN32 WIN32)
    # timegm is not available on Windows; use _mkgmtime instead
    add_compile_definitions(timegm=_mkgmtime)
    # tpl library compiled statically
    add_compile_definitions(TPL_NOLIB)
endif()

set(GOACCESS_EFFECTIVE_UTF8 OFF)

if(MINGW)
    # MinGW provides localtime_r under _POSIX_THREAD_SAFE_FUNCTIONS
    add_compile_definitions(_POSIX_THREAD_SAFE_FUNCTIONS)
endif()

# ============================================================
# Feature detection
# ============================================================
include(CheckIncludeFiles)
include(CheckFunctionExists)
include(CheckTypeSize)
include(CheckSymbolExists)
include(CheckLibraryExists)

set(GOACCESS_WIN_COMPAT_INCLUDE_DIR "")
set(GOACCESS_REQUIRED_INCLUDES "")
set(GOACCESS_REQUIRED_LIBRARIES "")
set(GOACCESS_ZLIB_INCLUDE_DIRS "")
set(GOACCESS_RUNTIME_LOCALEDIR "${CMAKE_INSTALL_FULL_LOCALEDIR}")

if(WIN32)
    # Mirror the effective MinGW build surface, not just the raw CRT surface.
    set(GOACCESS_WIN_COMPAT_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/src/win")
    list(APPEND GOACCESS_REQUIRED_INCLUDES "${GOACCESS_WIN_COMPAT_INCLUDE_DIR}")
    list(APPEND GOACCESS_REQUIRED_LIBRARIES ws2_32)
    # Use a build-local locale dir so gettext resources work before installation.
    set(GOACCESS_RUNTIME_LOCALEDIR "${CMAKE_CURRENT_BINARY_DIR}/locale")
endif()

set(CMAKE_REQUIRED_INCLUDES "${GOACCESS_REQUIRED_INCLUDES}")

check_include_files("fcntl.h"     HAVE_FCNTL_H)
check_include_files("iconv.h"     HAVE_ICONV_H)
check_include_files("inttypes.h"  HAVE_INTTYPES_H)
check_include_files("limits.h"    HAVE_LIMITS_H)
check_include_files("locale.h"    HAVE_LOCALE_H)
check_include_files("stddef.h"    HAVE_STDDEF_H)
check_include_files("stdint.h"    HAVE_STDINT_H)
check_include_files("stdlib.h"    HAVE_STDLIB_H)
check_include_files("string.h"    HAVE_STRING_H)
check_include_files("strings.h"   HAVE_STRINGS_H)
check_include_files("stdio.h"     HAVE_STDIO_H)
check_include_files("sys/stat.h"  HAVE_SYS_STAT_H)
check_include_files("sys/types.h" HAVE_SYS_TYPES_H)

# POSIX headers - may not be available on MSVC
check_include_files("unistd.h"       HAVE_UNISTD_H)
check_include_files("arpa/inet.h"    HAVE_ARPA_INET_H)
check_include_files("netdb.h"        HAVE_NETDB_H)
check_include_files("netinet/in.h"   HAVE_NETINET_IN_H)
check_include_files("sys/socket.h"   HAVE_SYS_SOCKET_H)
check_include_files("sys/time.h"     HAVE_SYS_TIME_H)
check_include_files("sys/param.h"    HAVE_SYS_PARAM_H)
check_include_files("getopt.h"       HAVE_GETOPT_H)

if(HAVE_ICONV_H)
    check_symbol_exists(iconv "iconv.h" HAVE_ICONV)
endif()

# ncurses / PDCurses detection - required for terminal UI
if(ENABLE_NCURSES)
    if(PDCURSES_SRC_DIR)
        # PDCurses submodule takes priority when specified
        include(cmake/BuildPDCurses.cmake)
        if(PDCurses_WIDE OR ENABLE_UTF8)
            set(HAVE_LIBNCURSESW 1)
            set(GOACCESS_EFFECTIVE_UTF8 ON)
        else()
            set(HAVE_LIBNCURSES 1)
        endif()
        set(HAVE_CURSES_H 1)
        set(CURSES_FOUND TRUE)
        set(CURSES_INCLUDE_DIR "${PDCURSES_SRC_DIR}")
        set(CURSES_LIBRARIES pdcurses)
    elseif(NOT GOACCESS_ALLOW_SYSTEM_DEPS)
        message(FATAL_ERROR "System curses/ncurses packages are not allowed; set PDCURSES_SRC_DIR to 3rdparty/PDCurses.")
    else()
        set(CURSES_NEED_NCURSES TRUE)
        find_package(Curses QUIET)

        if(CURSES_FOUND)
            if(ENABLE_UTF8 AND CURSES_HAVE_NCURSESW)
                set(HAVE_LIBNCURSESW 1)
                set(GOACCESS_EFFECTIVE_UTF8 ON)
            elseif(ENABLE_UTF8)
                check_include_files("ncursesw/ncurses.h" HAVE_NCURSESW_NCURSES_H)
                if(HAVE_NCURSESW_NCURSES_H)
                    set(HAVE_LIBNCURSESW 1)
                    set(GOACCESS_EFFECTIVE_UTF8 ON)
                else()
                    set(HAVE_LIBNCURSES 1)
                endif()
            else()
                set(HAVE_LIBNCURSES 1)
            endif()
        endif()

        if(NOT HAVE_LIBNCURSESW AND NOT HAVE_LIBNCURSES)
            if(WIN32)
                message(FATAL_ERROR
                    "ncurses/PDCurses not found. Terminal UI requires curses.\n"
                    "  Options:\n"
                    "    - Set -DPDCURSES_SRC_DIR=<path> to use PDCurses submodule\n"
                    "    - Install PDCurses (https://github.com/wmcbrine/PDCurses) for MSVC\n"
                    "    - Use MinGW with MSYS2 and install mingw-w64-ncurses\n"
                    "    - Or set -DENABLE_NCURSES=OFF (not yet supported)")
            else()
                message(FATAL_ERROR "ncurses library not found. Install ncurses-dev or set -DENABLE_NCURSES=OFF")
            endif()
        endif()
    endif()

    # Set HAVE_NCURSES_H / HAVE_CURSES_H based on what was found
    if(CURSES_INCLUDE_DIR)
        if(EXISTS "${CURSES_INCLUDE_DIR}/ncursesw/ncurses.h")
            set(HAVE_NCURSESW_NCURSES_H 1)
        endif()
        if(EXISTS "${CURSES_INCLUDE_DIR}/ncurses/ncurses.h")
            set(HAVE_NCURSES_NCURSES_H 1)
        endif()
        if(EXISTS "${CURSES_INCLUDE_DIR}/ncurses.h")
            set(HAVE_NCURSES_H 1)
        endif()
        if(EXISTS "${CURSES_INCLUDE_DIR}/curses.h")
            set(HAVE_CURSES_H 1)
        endif()
    endif()
endif()

# Function checks
set(CMAKE_REQUIRED_LIBRARIES "")
check_function_exists(malloc      HAVE_MALLOC)
check_function_exists(memmove     HAVE_MEMMOVE)
check_function_exists(memset      HAVE_MEMSET)
check_function_exists(realloc     HAVE_REALLOC)
check_function_exists(strchr      HAVE_STRCHR)
check_function_exists(strcspn     HAVE_STRCSPN)
check_function_exists(strdup      HAVE_STRDUP)
check_function_exists(strerror    HAVE_STRERROR)
check_function_exists(strstr      HAVE_STRSTR)
check_function_exists(strtol      HAVE_STRTOL)
check_function_exists(strtoull    HAVE_STRTOULL)
check_function_exists(floor       HAVE_FLOOR)
check_function_exists(gettimeofday HAVE_GETTIMEOFDAY)
check_function_exists(realpath    HAVE_REALPATH)

check_function_exists(strcasecmp  HAVE_STRCASECMP)
check_function_exists(strncasecmp HAVE_STRNCASECMP)
check_function_exists(strftime    HAVE_STRFTIME)
check_function_exists(timegm      HAVE_TIMEGM)
check_function_exists(setlocale   HAVE_SETLOCALE)

check_function_exists(fseeko      HAVE_FSEEKO)
check_function_exists(mkfifo      HAVE_MKFIFO)
check_function_exists(alarm       HAVE_ALARM)

set(CMAKE_REQUIRED_LIBRARIES "${GOACCESS_REQUIRED_LIBRARIES}")
check_function_exists(socket      HAVE_SOCKET)
check_function_exists(gethostbyname HAVE_GETHOSTBYNAME)
check_function_exists(gethostbyaddr HAVE_GETHOSTBYADDR)
set(CMAKE_REQUIRED_LIBRARIES "")

set(CMAKE_REQUIRED_INCLUDES "${GOACCESS_REQUIRED_INCLUDES}")
check_symbol_exists(poll "poll.h" HAVE_POLL)
check_symbol_exists(regcomp "regex.h" HAVE_REGCOMP)
if(WIN32 AND NOT HAVE_TIMEGM)
    check_symbol_exists(_mkgmtime "time.h" HAVE__MKGMTIME)
    if(HAVE__MKGMTIME)
        set(HAVE_TIMEGM 1)
    endif()
endif()
set(CMAKE_REQUIRED_INCLUDES "")

if(WIN32)
    # The MinGW build consumes the bundled compatibility layer under src/win.
    set(HAVE_ARPA_INET_H 1)
    set(HAVE_NETDB_H 1)
    set(HAVE_NETINET_IN_H 1)
    set(HAVE_SYS_SOCKET_H 1)
    set(HAVE_SOCKET 1)
    set(HAVE_GETHOSTBYNAME 1)
    set(HAVE_GETHOSTBYADDR 1)
    set(HAVE_MKFIFO 1)
    set(HAVE_POLL 1)
    set(HAVE_REALPATH 1)
    set(HAVE_REGCOMP 1)
    set(LSTAT_FOLLOWS_SLASHED_SYMLINK 1)
endif()

# SHA1 detection
check_include_files("sha.h"   HAVE_SHA_H)
check_include_files("sha1.h"  HAVE_SHA1_H)
check_function_exists(SHA1Init HAVE_SHA1INIT)
if(NOT HAVE_SHA1INIT)
    set(USE_SHA1 1)
endif()

# Check for fseeko
if(NOT HAVE_FSEEKO)
    check_symbol_exists(fseeko stdio.h HAVE_FSEEKO)
endif()

# ============================================================
# Optional dependency: OpenSSL
# ============================================================
if(WITH_SSL)
    if(NOT GOACCESS_ALLOW_SYSTEM_DEPS)
        message(FATAL_ERROR "System OpenSSL packages are not allowed; disable WITH_SSL or provide a vendored OpenSSL build.")
    endif()
    find_package(OpenSSL QUIET)
    if(OpenSSL_FOUND)
        set(HAVE_LIBSSL 1)
        set(HAVE_LIBCRYPTO 1)
        # Check for SSL_CIPHER_standard_name
        check_library_exists(ssl SSL_CIPHER_standard_name "" HAVE_CIPHER_STD_NAME)
    else()
        message(WARNING "OpenSSL not found. Disabling SSL support.")
        set(WITH_SSL OFF)
    endif()
endif()

# ============================================================
# Optional dependency: ZLIB
# ============================================================
if(WITH_ZLIB)
    if(ZLIB_SRC_DIR)
        set(ZLIB_BUILD_TESTING OFF CACHE BOOL "" FORCE)
        set(ZLIB_BUILD_SHARED ON CACHE BOOL "" FORCE)
        set(ZLIB_BUILD_STATIC OFF CACHE BOOL "" FORCE)
        set(ZLIB_INSTALL OFF CACHE BOOL "" FORCE)
        add_subdirectory("${ZLIB_SRC_DIR}" zlib_build EXCLUDE_FROM_ALL)
        set(HAVE_ZLIB 1)
        set(HAVE_LIBZ 1)
        set(ZLIB_FOUND TRUE)
        set(ZLIB_INCLUDE_DIRS "${ZLIB_SRC_DIR}")
        set(GOACCESS_ZLIB_INCLUDE_DIRS
            "${ZLIB_SRC_DIR}"
            "${CMAKE_CURRENT_BINARY_DIR}/zlib_build"
        )
    else()
        if(NOT GOACCESS_ALLOW_SYSTEM_DEPS)
            message(FATAL_ERROR "System zlib packages are not allowed; set ZLIB_SRC_DIR to 3rdparty/zlib.")
        endif()
        find_package(ZLIB QUIET)
        if(ZLIB_FOUND)
            set(HAVE_ZLIB 1)
            set(HAVE_LIBZ 1)
            set(GOACCESS_ZLIB_INCLUDE_DIRS ${ZLIB_INCLUDE_DIRS})
        else()
            message(WARNING "zlib not found. Disabling zlib support.")
            set(WITH_ZLIB OFF)
        endif()
    endif()
endif()

if(HAVE_ZLIB)
    set(CMAKE_REQUIRED_INCLUDES "${GOACCESS_REQUIRED_INCLUDES};${GOACCESS_ZLIB_INCLUDE_DIRS}")
    check_include_files("zlib.h" HAVE_ZLIB_H)
    set(CMAKE_REQUIRED_INCLUDES "")
endif()

# ============================================================
# Optional dependency: GeoIP
# ============================================================
if(ENABLE_GEOIP STREQUAL "mmdb")
    if(NOT GOACCESS_ALLOW_SYSTEM_DEPS)
        message(FATAL_ERROR "System GeoIP packages are not allowed; disable ENABLE_GEOIP or provide a vendored GeoIP build.")
    endif()
    find_library(MAXMINDDB_LIBRARY maxminddb)
    find_path(MAXMINDDB_INCLUDE_DIR maxminddb.h)
    if(MAXMINDDB_LIBRARY AND MAXMINDDB_INCLUDE_DIR)
        set(HAVE_GEOLOCATION 1)
        set(HAVE_LIBMAXMINDDB 1)
    else()
        message(WARNING "libmaxminddb not found. Disabling GeoIP.")
        set(ENABLE_GEOIP OFF)
    endif()
elseif(ENABLE_GEOIP STREQUAL "legacy")
    if(NOT GOACCESS_ALLOW_SYSTEM_DEPS)
        message(FATAL_ERROR "System GeoIP packages are not allowed; disable ENABLE_GEOIP or provide a vendored GeoIP build.")
    endif()
    find_library(GEOIP_LIBRARY GeoIP)
    find_path(GEOIP_INCLUDE_DIR GeoIP.h)
    if(GEOIP_LIBRARY AND GEOIP_INCLUDE_DIR)
        set(HAVE_GEOLOCATION 1)
        set(HAVE_LIBGEOIP 1)
    else()
        message(WARNING "GeoIP library not found. Disabling GeoIP.")
        set(ENABLE_GEOIP OFF)
    endif()
endif()

if(ENABLE_NLS)
    if(GETTEXT_SRC_DIR)
        set(HAVE_LIBINTL 1)
        set(HAVE_GETTEXT 1)
        set(HAVE_DCGETTEXT 1)
        if(NOT HAVE_ICONV)
            set(HAVE_ICONV 1)
        endif()
    elseif(GOACCESS_ALLOW_SYSTEM_DEPS)
        find_package(Intl QUIET)
        if(Intl_FOUND)
            set(HAVE_LIBINTL 1)
            set(HAVE_GETTEXT 1)
            set(HAVE_DCGETTEXT 1)
            if(NOT HAVE_ICONV)
                set(HAVE_ICONV 1)
            endif()
        endif()
    else()
        message(FATAL_ERROR "System gettext/intl packages are not allowed; set GETTEXT_SRC_DIR to 3rdparty/gettext or disable ENABLE_NLS.")
    endif()
endif()

# ============================================================
# Determine USE_MMAP (Windows needs custom mmap)
# ============================================================
if(WIN32)
    set(USE_MMAP 1)
endif()

# ============================================================
# Build config.h via cmake configure_file
# ============================================================
set(GOACCESS_CONFIG_ENABLE_NLS "")
if(ENABLE_NLS)
    set(GOACCESS_CONFIG_ENABLE_NLS 1)
endif()

set(GOACCESS_CONFIG_WITH_GETLINE "")
if(WITH_GETLINE)
    set(GOACCESS_CONFIG_WITH_GETLINE 1)
endif()

set(GOACCESS_CONFIG_DEBUG "")
if(ENABLE_DEBUG)
    set(GOACCESS_CONFIG_DEBUG 1)
endif()
set(_DEBUG "${GOACCESS_CONFIG_DEBUG}")

set(PACKAGE        "goaccess")
set(PACKAGE_NAME   "goaccess")
set(PACKAGE_TARNAME "goaccess")
set(PACKAGE_VERSION "1.10.2")
set(PACKAGE_STRING  "goaccess 1.10.2")
set(PACKAGE_BUGREPORT "hello@goaccess.io")
set(PACKAGE_URL     "https://goaccess.io")
set(VERSION         "1.10.2")

configure_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/config.h.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/config.h"
    @ONLY
)

# ============================================================
# bin2c build tool (used to embed resources as C headers)
# ============================================================
add_executable(bin2c EXCLUDE_FROM_ALL src/bin2c.c)
target_compile_definitions(bin2c PRIVATE $<$<BOOL:${WIN32}>:_CRT_SECURE_NO_WARNINGS>)
set_target_properties(bin2c PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
)

# ============================================================
# Generate resource header files using bin2c
# ============================================================
option(
    GOACCESS_REGENERATE_EMBEDDED_RESOURCES
    "Regenerate embedded resource headers in the source tree before building"
    OFF
)

# Maps: output_header <-- input_resource <-- variable_name
set(RESOURCE_MAP
    "src/tpls.h         resources/tpls.html              tpls"
    "src/bootstrapcss.h resources/css/bootstrap.min.css  bootstrap_css"
    "src/facss.h        resources/css/fa.min.css         fa_css"
    "src/appcss.h       resources/css/app.css            app_css"
    "src/d3js.h         resources/js/d3.v7.min.js        d3_js"
    "src/topojsonjs.h   resources/js/topojson.v3.min.js  topojson_js"
    "src/hoganjs.h      resources/js/hogan.min.js        hogan_js"
    "src/countries110m.h resources/countries-110m.json   countries_json"
    "src/cities10m.h    resources/cities-10m.json        cities_json"
    "src/chartsjs.h     resources/js/charts.js           charts_js"
    "src/appjs.h        resources/js/app.js              app_js"
)

set(GENERATED_RESOURCE_HEADERS)
foreach(RES_ENTRY ${RESOURCE_MAP})
    separate_arguments(RES_ENTRY_LIST NATIVE_COMMAND ${RES_ENTRY})
    list(GET RES_ENTRY_LIST 0 RES_HEADER)
    list(GET RES_ENTRY_LIST 1 RES_INPUT)
    list(GET RES_ENTRY_LIST 2 RES_VARNAME)

    set(RES_HEADER_PATH "${CMAKE_CURRENT_SOURCE_DIR}/${RES_HEADER}")
    set(RES_INPUT_PATH  "${CMAKE_CURRENT_SOURCE_DIR}/${RES_INPUT}")

    if(GOACCESS_REGENERATE_EMBEDDED_RESOURCES)
        add_custom_command(
            OUTPUT  "${RES_HEADER_PATH}"
            COMMAND "${CMAKE_CURRENT_BINARY_DIR}/bin2c${CMAKE_EXECUTABLE_SUFFIX}"
                    "${RES_INPUT_PATH}"
                    "${RES_HEADER_PATH}"
                    "${RES_VARNAME}"
            DEPENDS bin2c "${RES_INPUT_PATH}"
            COMMENT "Generating ${RES_HEADER} from ${RES_INPUT}"
        )
    elseif(NOT EXISTS "${RES_HEADER_PATH}")
        message(FATAL_ERROR
            "Missing pre-generated resource header: ${RES_HEADER_PATH}. "
            "Enable GOACCESS_REGENERATE_EMBEDDED_RESOURCES to rebuild embedded assets."
        )
    endif()

    list(APPEND GENERATED_RESOURCE_HEADERS "${RES_HEADER_PATH}")
endforeach()

# Also add the .tmp variant for clean
set(CLEAN_RESOURCE_TMP
    resources/tpls.html.tmp
    resources/countries-110m.json.tmp
    resources/cities-10m.json.tmp
    resources/css/bootstrap.min.css.tmp
    resources/css/fa.min.css.tmp
    resources/css/app.css.tmp
    resources/js/d3.v7.min.js.tmp
    resources/js/topojson.v3.min.js.tmp
    resources/js/hogan.min.js.tmp
    resources/js/charts.js.tmp
    resources/js/app.js.tmp
)

# ============================================================
# Main goaccess source files (from Makefile.am)
# ============================================================
set(GOACCESS_SOURCES
    src/base64.c
    src/browsers.c
    src/color.c
    src/commons.c
    src/csv.c
    src/dialogs.c
    src/error.c
    src/fileio.c
    src/gchart.c
    src/gdashboard.c
    src/gdns.c
    src/gholder.c
    src/gkhash.c
    src/gkmhash.c
    src/gmenu.c
    src/goaccess.c
    src/gslist.c
    src/gstorage.c
    src/gwsocket.c
    src/json.c
    src/opesys.c
    src/options.c
    src/output.c
    src/parser.c
    src/persistence.c
    src/pdjson.c
    src/settings.c
    src/sort.c
    src/tpl.c
    src/ui.c
    src/util.c
    src/websocket.c
    src/xmalloc.c
)

# Conditional sources
if(WITH_SSL)
    list(APPEND GOACCESS_SOURCES src/wsauth.c src/wsauth.h)
endif()

if(USE_SHA1)
    list(APPEND GOACCESS_SOURCES src/sha1.c src/sha1.h)
endif()

if(USE_MMAP)
    list(APPEND GOACCESS_SOURCES src/win/mmap.c)
endif()

# MSVC needs bundled getopt implementation
if(MSVC)
    list(APPEND GOACCESS_SOURCES src/win/getopt.c)
endif()

# Windows needs bundled POSIX regex (neither MSVC nor MinGW-w64 has it)
if(WIN32)
    list(APPEND GOACCESS_SOURCES src/win/regex.cpp)
    list(APPEND GOACCESS_SOURCES src/win/strptime.c)
endif()

if(ENABLE_GEOIP STREQUAL "legacy")
    list(APPEND GOACCESS_SOURCES src/geoip1.c src/geoip1.h)
elseif(ENABLE_GEOIP STREQUAL "mmdb")
    list(APPEND GOACCESS_SOURCES src/geoip2.c src/geoip1.h)
endif()

# Exclude ncurses-dependent files if ncurses not available
if(NOT ENABLE_NCURSES)
    list(REMOVE_ITEM GOACCESS_SOURCES
        src/ui.c
        src/gdashboard.c
        src/gmenu.c
        src/dialogs.c
        src/color.c
        src/gchart.c
    )
    # Stubs for non-ncurses builds
    list(APPEND GOACCESS_SOURCES src/noncurses_stubs.c)
endif()

# ============================================================
# Main goaccess executable
# ============================================================
add_executable(goaccess
    ${GOACCESS_SOURCES}
    ${GENERATED_RESOURCE_HEADERS}
)

# regex.cpp uses C++ std::regex - force CXX language
if(WIN32)
    set_source_files_properties(
        "${CMAKE_CURRENT_SOURCE_DIR}/src/win/regex.cpp"
        PROPERTIES LANGUAGE CXX
    )
endif()

target_include_directories(goaccess PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/src"
    "${CMAKE_CURRENT_BINARY_DIR}"
)

# Add curses include directory if found
if(CURSES_INCLUDE_DIR)
    target_include_directories(goaccess PRIVATE ${CURSES_INCLUDE_DIR})
endif()

# On Windows, add win/ compat headers to include path
if(WIN32)
    target_include_directories(goaccess PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/src/win"
    )
endif()

target_compile_definitions(goaccess PRIVATE
    HAVE_CONFIG_H=1
    $<$<BOOL:${ENABLE_NLS}>:ENABLE_NLS>
    $<$<BOOL:${WITH_GETLINE}>:WITH_GETLINE>
    $<$<BOOL:${ENABLE_DEBUG}>:_DEBUG>
    $<$<BOOL:${ENABLE_DEBUG}>:DEBUG>
    $<$<BOOL:${USE_MMAP}>:USE_MMAP>
    $<$<STREQUAL:${ENABLE_GEOIP},legacy>:HAVE_GEOLOCATION>
    $<$<STREQUAL:${ENABLE_GEOIP},legacy>:HAVE_LIBGEOIP>
    $<$<STREQUAL:${ENABLE_GEOIP},mmdb>:HAVE_GEOLOCATION>
    $<$<STREQUAL:${ENABLE_GEOIP},mmdb>:HAVE_LIBMAXMINDDB>
    $<$<BOOL:${WITH_SSL}>:HAVE_LIBSSL>
    $<$<BOOL:${WITH_SSL}>:HAVE_LIBCRYPTO>
    $<$<BOOL:${HAVE_ZLIB}>:HAVE_ZLIB>
    $<$<BOOL:${HAVE_CIPHER_STD_NAME}>:HAVE_CIPHER_STD_NAME>
    $<$<NOT:$<BOOL:${HAVE_SHA1INIT}>>:USE_SHA1>
    $<$<BOOL:${HAVE_LIBNCURSESW}>:HAVE_LIBNCURSESW>
    $<$<BOOL:${HAVE_LIBNCURSES}>:HAVE_LIBNCURSES>
    $<$<BOOL:${HAVE_NCURSESW_NCURSES_H}>:HAVE_NCURSESW_NCURSES_H>
    $<$<BOOL:${HAVE_NCURSES_H}>:HAVE_NCURSES_H>
    $<$<BOOL:${HAVE_CURSES_H}>:HAVE_CURSES_H>
)

if(MSVC)
    target_compile_definitions(goaccess PRIVATE
        _CRT_SECURE_NO_WARNINGS
        _CRT_NONSTDC_NO_WARNINGS
    )
endif()

# Compile options
if(MSVC)
    target_compile_options(goaccess PRIVATE /W0)
else()
    target_compile_options(goaccess PRIVATE
        -Wall -Wextra -Wnested-externs -Wformat=2
        -Wmissing-prototypes -Wstrict-prototypes -Wmissing-declarations
        -Wwrite-strings -Wshadow -Wpointer-arith -Wsign-compare
        -Wbad-function-cast -Wcast-align
        -Wdeclaration-after-statement -Wold-style-definition
    )
endif()

if(ENABLE_DEBUG)
    target_compile_options(goaccess PRIVATE -O0 -g)
    if(GOACCESS_ENABLE_ASAN AND NOT MSVC)
        target_compile_options(goaccess PRIVATE -fsanitize=address)
        target_link_options(goaccess PRIVATE -fsanitize=address)
    endif()
else()
    if(MSVC)
        target_compile_options(goaccess PRIVATE /O2)
    else()
        target_compile_options(goaccess PRIVATE -O2)
    endif()
endif()

# ============================================================
# Link libraries
# ============================================================
if(NOT MSVC)
    target_link_libraries(goaccess PRIVATE m)
endif()

if(WIN32)
    target_link_libraries(goaccess PRIVATE ws2_32)
endif()

# Threading - uses pthreads API
if(MSVC)
    # MSVC needs a pthreads port (e.g., pthreads-w32 or winpthreads)
    find_library(PTHREAD_LIB pthreadVC2)
    if(NOT PTHREAD_LIB)
        find_library(PTHREAD_LIB pthread)
    endif()
    if(PTHREAD_LIB)
        target_link_libraries(goaccess PRIVATE ${PTHREAD_LIB})
    else()
        message(FATAL_ERROR "pthreads library not found. For MSVC, install pthreads4w or use MinGW.")
    endif()
else()
    find_package(Threads REQUIRED)
    target_link_libraries(goaccess PRIVATE Threads::Threads)
endif()

if(HAVE_LIBNCURSESW OR HAVE_LIBNCURSES)
    if(NCURSESW_FOUND OR HAVE_LIBNCURSESW)
        if(NCURSESW_FOUND)
            target_include_directories(goaccess PRIVATE ${NCURSESW_INCLUDE_DIRS})
            target_link_libraries(goaccess PRIVATE ${NCURSESW_LIBRARIES})
        elseif(CURSES_FOUND)
            target_include_directories(goaccess PRIVATE ${CURSES_INCLUDE_DIR})
            target_link_libraries(goaccess PRIVATE ${CURSES_LIBRARIES})
        else()
            target_link_libraries(goaccess PRIVATE ncursesw)
        endif()
        if(NOT WIN32)
            find_library(TINFOW_LIBRARY tinfow)
            if(TINFOW_LIBRARY)
                target_link_libraries(goaccess PRIVATE ${TINFOW_LIBRARY})
            endif()
        endif()
    elseif(HAVE_LIBNCURSES)
        if(CURSES_FOUND)
            target_include_directories(goaccess PRIVATE ${CURSES_INCLUDE_DIR})
            target_link_libraries(goaccess PRIVATE ${CURSES_LIBRARIES})
        else()
            target_link_libraries(goaccess PRIVATE ncurses)
        endif()
        if(NOT WIN32)
            find_library(TINFO_LIBRARY tinfo)
            if(TINFO_LIBRARY)
                target_link_libraries(goaccess PRIVATE ${TINFO_LIBRARY})
            endif()
        endif()
    endif()
endif()

if(WITH_SSL AND OpenSSL_FOUND)
    target_include_directories(goaccess PRIVATE ${OpenSSL_INCLUDE_DIR})
    target_link_libraries(goaccess PRIVATE OpenSSL::SSL OpenSSL::Crypto)
endif()

if(WITH_ZLIB AND ZLIB_FOUND)
    if(ZLIB_SRC_DIR)
        target_include_directories(goaccess PRIVATE "${ZLIB_SRC_DIR}")
    else()
        target_include_directories(goaccess PRIVATE ${ZLIB_INCLUDE_DIRS})
    endif()
    target_link_libraries(goaccess PRIVATE ZLIB::ZLIB)
    if(WIN32 AND ZLIB_SRC_DIR)
        add_custom_command(TARGET goaccess POST_BUILD
            COMMAND "${CMAKE_COMMAND}" -E copy_if_different
                "$<TARGET_FILE:zlib>"
                "$<TARGET_FILE_DIR:goaccess>"
            COMMENT "Copying libz.dll to output dir"
        )
    endif()
endif()

if(ENABLE_GEOIP STREQUAL "mmdb" AND MAXMINDDB_LIBRARY)
    target_include_directories(goaccess PRIVATE ${MAXMINDDB_INCLUDE_DIR})
    target_link_libraries(goaccess PRIVATE ${MAXMINDDB_LIBRARY})
elseif(ENABLE_GEOIP STREQUAL "legacy" AND GEOIP_LIBRARY)
    target_include_directories(goaccess PRIVATE ${GEOIP_INCLUDE_DIR})
    target_link_libraries(goaccess PRIVATE ${GEOIP_LIBRARY})
endif()

if(ENABLE_NLS)
    if(Intl_FOUND)
        target_link_libraries(goaccess PRIVATE Intl::Intl)
    elseif(GETTEXT_SRC_DIR)
        include(cmake/BuildLibintl.cmake)
        target_link_libraries(goaccess PRIVATE libintl)
    else()
        target_link_libraries(goaccess PRIVATE intl)
    endif()
endif()

# ============================================================
# Compile-time defines from config.h (via compile defs)
# ============================================================
target_compile_definitions(goaccess PRIVATE
    SYSCONFDIR="${CMAKE_INSTALL_FULL_SYSCONFDIR}"
    LOCALEDIR="${GOACCESS_RUNTIME_LOCALEDIR}"
    $<$<BOOL:${MINGW}>:NCURSES_MOUSE_VERSION=2>
)

# ============================================================
# Resource header dependency: output.c depends on generated headers
# ============================================================
if(GENERATED_RESOURCE_HEADERS)
    set_source_files_properties(
        ${CMAKE_CURRENT_SOURCE_DIR}/src/output.c
        PROPERTIES OBJECT_DEPENDS "${GENERATED_RESOURCE_HEADERS}"
    )
endif()

# ============================================================
# Install rules
# ============================================================
install(TARGETS goaccess RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(FILES config/goaccess.conf DESTINATION ${CMAKE_INSTALL_SYSCONFDIR}/goaccess)
install(FILES config/browsers.list DESTINATION ${CMAKE_INSTALL_SYSCONFDIR}/goaccess)
install(FILES config/podcast.list DESTINATION ${CMAKE_INSTALL_SYSCONFDIR}/goaccess)

# ============================================================
# Print configuration summary
# ============================================================
message(STATUS "")
message(STATUS "GoAccess ${PROJECT_VERSION} Configuration Summary")
message(STATUS "=================================")
message(STATUS "  Compiler        : ${CMAKE_C_COMPILER}")
message(STATUS "  Terminal UI     : ${ENABLE_NCURSES}")
message(STATUS "  UTF-8 support   : ${GOACCESS_EFFECTIVE_UTF8}")
message(STATUS "  Dynamic buffer  : ${WITH_GETLINE}")
message(STATUS "  Debug           : ${ENABLE_DEBUG}")
message(STATUS "  Geolocation     : ${ENABLE_GEOIP}")
message(STATUS "  TLS/SSL         : ${WITH_SSL}")
message(STATUS "  zlib support    : ${WITH_ZLIB}")
message(STATUS "  NLS             : ${ENABLE_NLS}")
message(STATUS "  MMAP (Win)      : ${USE_MMAP}")
message(STATUS "=================================")
message(STATUS "")
