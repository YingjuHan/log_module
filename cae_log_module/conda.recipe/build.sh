#!/usr/bin/env bash
set -euxo pipefail

cmake -S . -B build -G Ninja \
    -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
    -DCMAKE_PREFIX_PATH="${PREFIX}" \
    -DBOOST_ROOT="${PREFIX}" \
    -DCAE_LOGGER_BUILD_DOCS=OFF \
    -DCAE_LOGGER_INSTALL_DOCS=OFF \
    -DCAE_LOGGER_INSTALL_TEST_PROJECT=OFF \
    -DCMAKE_BUILD_TYPE=Release

cmake --build build --parallel
cmake --install build
