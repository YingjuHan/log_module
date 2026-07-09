#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
config=Debug
build_dir=
install_prefix=
generator=
generator_platform=
generator_toolset=
clean=0
dry_run=0

usage() {
    cat <<EOF
Usage: ./build.sh [options]

Options:
  --config <Debug|Release>       Build configuration (default: Debug)
  --build-dir <dir>              Build directory (default: build/<config>)
  --install-prefix <dir>         Install prefix (default: install/<config>)
  --generator <name>             CMake generator
  --generator-platform <name>    CMake -A value
  --generator-toolset <name>     CMake -T value
  --clean                        Remove this project's build/install dirs first
  --dry-run                      Print commands without running them
  --help                         Show this help
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --config) config=$2; shift 2 ;;
        --build-dir) build_dir=$2; shift 2 ;;
        --install-prefix) install_prefix=$2; shift 2 ;;
        --generator) generator=$2; shift 2 ;;
        --generator-platform) generator_platform=$2; shift 2 ;;
        --generator-toolset) generator_toolset=$2; shift 2 ;;
        --clean) clean=1; shift ;;
        --dry-run) dry_run=1; shift ;;
        --help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

[ -n "$build_dir" ] || build_dir="$script_dir/build/$config"
[ -n "$install_prefix" ] || install_prefix="$script_dir/install/$config"

if [ "$config" = "Debug" ]; then
    enable_debug=ON
else
    enable_debug=OFF
fi

run() {
    printf '+'
    for arg in "$@"; do
        printf ' %s' "$arg"
    done
    printf '\n'
    [ "$dry_run" -eq 1 ] || "$@"
}

if [ "$clean" -eq 1 ]; then
    run cmake -E rm -rf "$build_dir" "$install_prefix"
fi

configure_args=()
if [ -n "$generator" ]; then
    configure_args+=("-G" "$generator")
fi
if [ -n "$generator_platform" ]; then
    configure_args+=("-A" "$generator_platform")
fi
if [ -n "$generator_toolset" ]; then
    configure_args+=("-T" "$generator_toolset")
fi

run cmake ${configure_args[@]+"${configure_args[@]}"} -S "$script_dir" -B "$build_dir" \
    -DCMAKE_BUILD_TYPE="$config" \
    -DCMAKE_INSTALL_PREFIX="$install_prefix" \
    -DENABLE_DEBUG="$enable_debug" \
    -DENABLE_NCURSES=ON \
    -DWITH_ZLIB=ON \
    -DENABLE_NLS=OFF \
    -DGOACCESS_ALLOW_SYSTEM_DEPS=OFF \
    -DGOACCESS_REGENERATE_EMBEDDED_RESOURCES=OFF \
    -DGETTEXT_SRC_DIR="$script_dir/thirdparty/gettext" \
    -DZLIB_SRC_DIR="$script_dir/thirdparty/zlib" \
    -DPDCURSES_SRC_DIR="$script_dir/thirdparty/PDCurses"
run cmake --build "$build_dir" --config "$config" --target goaccess
run cmake --install "$build_dir" --config "$config" --prefix "$install_prefix"

exe_name=goaccess
if [ -f "$build_dir/$config/$exe_name" ]; then
    goaccess_exe="$build_dir/$config/$exe_name"
elif [ -f "$build_dir/$exe_name" ]; then
    goaccess_exe="$build_dir/$exe_name"
else
    goaccess_exe="$install_prefix/bin/$exe_name"
fi

if [ "$dry_run" -eq 0 ]; then
    [ -f "$build_dir/CMakeCache.txt" ] || { echo "GoAccess CMake cache not found: $build_dir/CMakeCache.txt" >&2; exit 1; }
    [ -f "$goaccess_exe" ] || { echo "GoAccess executable not found: $goaccess_exe" >&2; exit 1; }
fi
