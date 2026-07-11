#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
initial_dir=$(pwd)
config=Debug
build_dir=
install_prefix=
generator=
prefix_path=${CAE_LOGGER_PREFIX_PATH:-}
clean=0
dry_run=0

usage() {
    cat <<EOF
Usage: ./build.sh [options]

Options:
  --config <Debug|Release>       Build configuration (default: Debug)
  --build-dir <dir>              Build directory (default: build/<config>)
  --install-prefix <dir>         Install prefix (default: install/<config>)
  --generator <name>             CMake generator, for example "MinGW Makefiles"
  --prefix-path <path>           CMake dependency prefix (or set CAE_LOGGER_PREFIX_PATH)
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
        --prefix-path) prefix_path=$2; shift 2 ;;
        --clean) clean=1; shift ;;
        --dry-run) dry_run=1; shift ;;
        --help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

[ -n "$build_dir" ] || build_dir="$script_dir/build/$config"
[ -n "$install_prefix" ] || install_prefix="$script_dir/install/$config"

abs_path() {
    case "$1" in
        /* | [A-Za-z]:*) printf '%s\n' "$1" ;;
        *) printf '%s\n' "$initial_dir/$1" ;;
    esac
}

build_dir=$(abs_path "$build_dir")
install_prefix=$(abs_path "$install_prefix")

run() {
    printf '+'
    for arg in "$@"; do
        printf ' %s' "$arg"
    done
    printf '\n'
    [ "$dry_run" -eq 1 ] || "$@"
}

run_in_dir() {
    work_dir=$1
    shift

    printf '+ cd %s &&' "$work_dir"
    for arg in "$@"; do
        printf ' %s' "$arg"
    done
    printf '\n'

    [ "$dry_run" -eq 1 ] || (cd "$work_dir" && "$@")
}

if [ "$clean" -eq 1 ]; then
    run cmake -E remove_directory "$build_dir"
    run cmake -E remove_directory "$install_prefix"
fi

configure_args=()
if [ -n "$generator" ]; then
    configure_args+=("-G" "$generator")
fi
if [ -n "$prefix_path" ]; then
    configure_args+=("-DCMAKE_PREFIX_PATH=$prefix_path")
fi

run cmake -E make_directory "$build_dir"
run_in_dir "$build_dir" cmake ${configure_args[@]+"${configure_args[@]}"} \
    -DCMAKE_BUILD_TYPE="$config" \
    -DCMAKE_INSTALL_PREFIX="$install_prefix" \
    "$script_dir"
run cmake --build "$build_dir" --config "$config" --target cae_logger -j8
run cmake --build "$build_dir" --config "$config" --target install

package_config="$install_prefix/lib/cmake/cae_logger/cae_loggerConfig.cmake"
package_config_lib64="$install_prefix/lib64/cmake/cae_logger/cae_loggerConfig.cmake"
if [ "$dry_run" -eq 0 ] && [ ! -f "$package_config" ] && [ ! -f "$package_config_lib64" ]; then
    echo "cae_logger package config not found under lib or lib64: $install_prefix" >&2
    exit 1
fi
