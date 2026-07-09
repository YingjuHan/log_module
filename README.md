# log_module

This repository is split into three independent projects. Each project owns its
source, configuration, dependencies, scripts, and build outputs.

## Layout

- `cae_log_module/`: the `cae_logger` C++ library, its CMake package config,
  runtime config, docs, and local dependency headers.
  `spdlog` is supplied through a configurable header include directory or as an
  explicit CMake package; it is not added to the `cae_logger` build as source.
- `goaccess/`: the GoAccess log analysis executable and its own vendored
  `gettext`/`zlib`/`PDCurses` dependencies.
- `test/`: sample applications, CTest smoke tests, Python e2e/reporting tools,
  schemas, GoAccess profile config, and test outputs.

The repository root is only a coordination layer. Do not place build products,
logs, reports, or source-owned config files at the root.

## Build

Build the library:

```cmd
cae_log_module\build.cmd --config Debug --install-prefix cae_log_module\install\Debug ^
  --spdlog-include-dir D:\deps\spdlog\include
```

```sh
./cae_log_module/build.sh --config Debug --install-prefix cae_log_module/install/Debug \
  --spdlog-include-dir /opt/spdlog/include
```

Windows `build.cmd` supports explicit MinGW generator selection. When you switch
to a different generator, do not reuse a build directory that was already
configured by CMake with another generator.

```cmd
cae_log_module\build.cmd --config Debug ^
  --build-dir cae_log_module\build\Debug-mingw ^
  --install-prefix cae_log_module\install\Debug ^
  --generator "MinGW Makefiles" ^
  --spdlog-include-dir D:\deps\spdlog\include
```

Use `--clean` if you want the script to recreate the build and install folders:

```cmd
cae_log_module\build.cmd --config Debug ^
  --install-prefix cae_log_module\install\Debug ^
  --generator "MinGW Makefiles" ^
  --spdlog-include-dir D:\deps\spdlog\include ^
  --clean
```

Configure spdlog explicitly with a checkout or install tree whose headers live
under `<dir>/spdlog`:

```cmd
cae_log_module\build.cmd --config Debug ^
  --spdlog-include-dir D:\deps\spdlog\include
```

```sh
./cae_log_module/build.sh --config Debug \
  --spdlog-include-dir /opt/spdlog/include
```

Build GoAccess:

```cmd
goaccess\build.cmd --config Debug --install-prefix goaccess\install\Debug
```

```sh
./goaccess/build.sh --config Debug --install-prefix goaccess/install/Debug
```

Build and verify the test project:

```cmd
test\build.cmd --config Debug ^
  --cae-logger-dir cae_log_module\install\Debug\lib\cmake\cae_logger ^
  --goaccess-exe goaccess\build\Debug\goaccess.exe
```

```sh
./test/build.sh --config Debug \
  --cae-logger-dir cae_log_module/install/Debug/lib/cmake/cae_logger \
  --goaccess-exe goaccess/build/Debug/goaccess
```

Each script supports `--dry-run` to print the CMake/Python commands without
running them.

## Outputs

- `cae_log_module/build/<Config>/` and `cae_log_module/install/<Config>/`
- `goaccess/build/<Config>/` and `goaccess/install/<Config>/`
- `test/build/<Config>/` and `test/out/`

`test/out/cae_manifest.json` records the exact test executable, GoAccess
executable, logs, reports, and config paths used by Python e2e verification.

## Python Tools

Python tooling lives under `test/tools` and is for testing, log processing,
reporting, and e2e verification only. Build actions are delegated to
`test/build.cmd` or `test/build.sh`; call those scripts directly for builds.

From `test/`:

```cmd
build.cmd --config Debug --skip-e2e
build.cmd --config Debug --ctest-only
python -m tools.cae verify --manifest out\cae_manifest.json
```
