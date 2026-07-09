#!/usr/bin/env bash
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
workspace_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
initial_dir=$(pwd)

config=Debug
build_dir=
out_dir="$script_dir/out"
manifest=
cae_logger_dir=
cae_logger_config=
goaccess_exe=
generator=
clean=0
dry_run=0
skip_ctest=0
skip_e2e=0
ctest_only=0
skip_probes=0
minimum_lines=1600

usage() {
    cat <<EOF
Usage: ./build.sh [options]

Options:
  --config <Debug|Release>       Build configuration (default: Debug)
  --build-dir <dir>              Test build directory (default: build/<config>)
  --out-dir <dir>                Test output directory (default: out)
  --manifest <file>              Manifest path (default: out/cae_manifest.json)
  --cae-logger-dir <dir>         Installed cae_logger CMake package directory
  --cae-logger-config <file>     Installed cae_logger runtime config file
  --goaccess-exe <file>          Built GoAccess executable
  --generator <name>             CMake generator
  --clean                        Remove this project's build/out dirs first
  --skip-ctest                   Do not run CTest
  --skip-e2e                     Do not run Python e2e verification
  --ctest-only                   Run CTest only against an existing test build
  --minimum-lines <count>        e2e minimum merged event count
  --skip-probes                  Forward to Python e2e verification
  --dry-run                      Print commands without running them
  --help                         Show this help
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --config) config=$2; shift 2 ;;
        --build-dir) build_dir=$2; shift 2 ;;
        --out-dir) out_dir=$2; shift 2 ;;
        --manifest) manifest=$2; shift 2 ;;
        --cae-logger-dir) cae_logger_dir=$2; shift 2 ;;
        --cae-logger-config) cae_logger_config=$2; shift 2 ;;
        --goaccess-exe) goaccess_exe=$2; shift 2 ;;
        --generator) generator=$2; shift 2 ;;
        --clean) clean=1; shift ;;
        --skip-ctest) skip_ctest=1; shift ;;
        --skip-e2e) skip_e2e=1; shift ;;
        --ctest-only) ctest_only=1; shift ;;
        --minimum-lines) minimum_lines=$2; shift 2 ;;
        --skip-probes) skip_probes=1; shift ;;
        --dry-run) dry_run=1; shift ;;
        --help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

[ -n "$build_dir" ] || build_dir="$script_dir/build/$config"
[ -n "$manifest" ] || manifest="$out_dir/cae_manifest.json"
[ -n "$cae_logger_dir" ] || cae_logger_dir="$workspace_dir/cae_log_module/install/$config/lib/cmake/cae_logger"
if [ ! -f "$cae_logger_dir/cae_loggerConfig.cmake" ] \
    && [ -f "$workspace_dir/cae_log_module/install/$config/lib64/cmake/cae_logger/cae_loggerConfig.cmake" ]; then
    cae_logger_dir="$workspace_dir/cae_log_module/install/$config/lib64/cmake/cae_logger"
fi
install_prefix_candidate=$(CDPATH= cd -- "$script_dir/../../.." && pwd)
if [ ! -f "$cae_logger_dir/cae_loggerConfig.cmake" ] \
    && [ -f "$install_prefix_candidate/lib/cmake/cae_logger/cae_loggerConfig.cmake" ]; then
    cae_logger_dir="$install_prefix_candidate/lib/cmake/cae_logger"
fi
if [ ! -f "$cae_logger_dir/cae_loggerConfig.cmake" ] \
    && [ -f "$install_prefix_candidate/lib64/cmake/cae_logger/cae_loggerConfig.cmake" ]; then
    cae_logger_dir="$install_prefix_candidate/lib64/cmake/cae_logger"
fi
if [ -z "$goaccess_exe" ]; then
    case "$(uname -s 2>/dev/null || true)" in
        MINGW* | MSYS* | CYGWIN*) goaccess_exe="$workspace_dir/goaccess/build/$config/goaccess.exe" ;;
        *) goaccess_exe="$workspace_dir/goaccess/build/$config/goaccess" ;;
    esac
fi

abs_path() {
    case "$1" in
        /* | [A-Za-z]:*) printf '%s\n' "$1" ;;
        *) printf '%s\n' "$initial_dir/$1" ;;
    esac
}

build_dir=$(abs_path "$build_dir")
out_dir=$(abs_path "$out_dir")
manifest=$(abs_path "$manifest")
cae_logger_dir=$(abs_path "$cae_logger_dir")
goaccess_exe=$(abs_path "$goaccess_exe")
if [ -n "$cae_logger_config" ]; then
    cae_logger_config=$(abs_path "$cae_logger_config")
fi

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

if [ "$clean" -eq 1 ] && [ "$ctest_only" -eq 0 ]; then
    run cmake -E remove_directory "$build_dir"
    run cmake -E remove_directory "$out_dir"
fi

if [ "$ctest_only" -eq 0 ]; then
    if [ "$dry_run" -eq 0 ]; then
        [ -f "$cae_logger_dir/cae_loggerConfig.cmake" ] || { echo "cae_loggerConfig.cmake not found under: $cae_logger_dir" >&2; exit 1; }
        if [ "$skip_e2e" -eq 0 ]; then
            [ -f "$goaccess_exe" ] || { echo "GoAccess executable not found: $goaccess_exe" >&2; exit 1; }
        fi
    fi

    configure_args=()
    if [ -n "$generator" ]; then
        configure_args+=("-G" "$generator")
    fi

    cmake_options=(-D"CMAKE_BUILD_TYPE=$config" -D"cae_logger_DIR=$cae_logger_dir")
    if [ -n "$cae_logger_config" ]; then
        cmake_options+=(-D"CAE_LOGGER_CONFIG_FILE=$cae_logger_config")
    fi

    run cmake -E make_directory "$build_dir"
    run_in_dir "$build_dir" cmake ${configure_args[@]+"${configure_args[@]}"} "${cmake_options[@]}" "$script_dir"
    run cmake --build "$build_dir" --config "$config"
fi

if [ "$skip_ctest" -eq 0 ]; then
    run_in_dir "$build_dir" ctest -C "$config" --output-on-failure
fi

if [ "$ctest_only" -eq 1 ]; then
    exit 0
fi

app_exe="$build_dir/app_main"
if [ -f "$build_dir/app_main.exe" ]; then
    app_exe="$build_dir/app_main.exe"
elif [ -f "$build_dir/$config/app_main.exe" ]; then
    app_exe="$build_dir/$config/app_main.exe"
elif [ -f "$build_dir/$config/app_main" ]; then
    app_exe="$build_dir/$config/app_main"
fi
app_config_dir=$(dirname -- "$app_exe")
goaccess_build_dir=$(dirname -- "$goaccess_exe")

run cmake \
    -DMANIFEST_PATH="$manifest" \
    -DAPP_EXE="$app_exe" \
    -DAPP_BUILD_DIR="$build_dir" \
    -DAPP_CONFIG_DIR="$app_config_dir" \
    -DCAE_LOGGER_DIR="$cae_logger_dir" \
    -DGOACCESS_EXE="$goaccess_exe" \
    -DGOACCESS_BUILD_DIR="$goaccess_build_dir" \
    -DGOACCESS_SOURCE_DIR="$workspace_dir/goaccess" \
    -DLOGS_DIR="$out_dir/logs" \
    -DREPORTS_DIR="$out_dir/reports" \
    -DPROFILE_CONFIG="$script_dir/config/cae_goaccess.conf" \
    -DTEST_CONFIG="$config" \
    -P "$script_dir/cmake/write_cae_manifest.cmake"

if [ "$skip_e2e" -eq 0 ]; then
    e2e_args=(env "PYTHONPATH=$script_dir${PYTHONPATH:+:$PYTHONPATH}" python -m tools.verify.e2e_verify --manifest "$manifest" --minimum-lines "$minimum_lines")
    if [ "$skip_probes" -eq 1 ]; then
        e2e_args+=(--skip-probes)
    fi
    run "${e2e_args[@]}"
fi
