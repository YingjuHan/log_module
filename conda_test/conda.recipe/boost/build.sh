#!/usr/bin/env bash
set -euxo pipefail

./bootstrap.sh
./b2 \
  --prefix="${PREFIX}" \
  install \
  variant=release \
  threading=multi \
  link=shared \
  runtime-link=shared \
  address-model=64 \
  layout=tagged
