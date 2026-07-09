@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "WORKSPACE_DIR=%%~fI"

set "CONFIG=Debug"
set "BUILD_DIR="
set "OUT_DIR=%SCRIPT_DIR%\out"
set "MANIFEST="
set "CAE_LOGGER_DIR="
set "CAE_LOGGER_CONFIG="
set "GOACCESS_EXE="
set "GENERATOR="
set "CLEAN=0"
set "DRY_RUN=0"
set "SKIP_CTEST=0"
set "SKIP_E2E=0"
set "CTEST_ONLY=0"
set "SKIP_PROBES=0"
set "MINIMUM_LINES=1600"

:parse
if "%~1"=="" goto after_parse
if /I "%~1"=="--config" set "CONFIG=%~2" & shift & shift & goto parse
if /I "%~1"=="--build-dir" set "BUILD_DIR=%~2" & shift & shift & goto parse
if /I "%~1"=="--out-dir" set "OUT_DIR=%~2" & shift & shift & goto parse
if /I "%~1"=="--manifest" set "MANIFEST=%~2" & shift & shift & goto parse
if /I "%~1"=="--cae-logger-dir" set "CAE_LOGGER_DIR=%~2" & shift & shift & goto parse
if /I "%~1"=="--cae-logger-config" set "CAE_LOGGER_CONFIG=%~2" & shift & shift & goto parse
if /I "%~1"=="--goaccess-exe" set "GOACCESS_EXE=%~2" & shift & shift & goto parse
if /I "%~1"=="--generator" set "GENERATOR=%~2" & shift & shift & goto parse
if /I "%~1"=="--clean" set "CLEAN=1" & shift & goto parse
if /I "%~1"=="--skip-ctest" set "SKIP_CTEST=1" & shift & goto parse
if /I "%~1"=="--skip-e2e" set "SKIP_E2E=1" & shift & goto parse
if /I "%~1"=="--ctest-only" set "CTEST_ONLY=1" & shift & goto parse
if /I "%~1"=="--minimum-lines" set "MINIMUM_LINES=%~2" & shift & shift & goto parse
if /I "%~1"=="--skip-probes" set "SKIP_PROBES=1" & shift & goto parse
if /I "%~1"=="--dry-run" set "DRY_RUN=1" & shift & goto parse
if /I "%~1"=="--help" goto usage
echo Unknown option: %~1 1>&2
goto usage_error

:after_parse
if not defined BUILD_DIR set "BUILD_DIR=%SCRIPT_DIR%\build\%CONFIG%"
if not defined MANIFEST set "MANIFEST=%OUT_DIR%\cae_manifest.json"
if not defined CAE_LOGGER_DIR set "CAE_LOGGER_DIR=%WORKSPACE_DIR%\cae_log_module\install\%CONFIG%\lib\cmake\cae_logger"
if not exist "%CAE_LOGGER_DIR%\cae_loggerConfig.cmake" for %%I in ("%SCRIPT_DIR%\..\..\..") do set "INSTALL_PREFIX_CANDIDATE=%%~fI"
if not exist "%CAE_LOGGER_DIR%\cae_loggerConfig.cmake" if exist "%INSTALL_PREFIX_CANDIDATE%\lib\cmake\cae_logger\cae_loggerConfig.cmake" set "CAE_LOGGER_DIR=%INSTALL_PREFIX_CANDIDATE%\lib\cmake\cae_logger"
if not exist "%CAE_LOGGER_DIR%\cae_loggerConfig.cmake" if exist "%INSTALL_PREFIX_CANDIDATE%\lib64\cmake\cae_logger\cae_loggerConfig.cmake" set "CAE_LOGGER_DIR=%INSTALL_PREFIX_CANDIDATE%\lib64\cmake\cae_logger"
if not defined GOACCESS_EXE set "GOACCESS_EXE=%WORKSPACE_DIR%\goaccess\build\%CONFIG%\goaccess.exe"

for %%I in ("%BUILD_DIR%") do set "BUILD_DIR=%%~fI"
for %%I in ("%OUT_DIR%") do set "OUT_DIR=%%~fI"
for %%I in ("%MANIFEST%") do set "MANIFEST=%%~fI"
for %%I in ("%CAE_LOGGER_DIR%") do set "CAE_LOGGER_DIR=%%~fI"
if defined CAE_LOGGER_CONFIG for %%I in ("%CAE_LOGGER_CONFIG%") do set "CAE_LOGGER_CONFIG=%%~fI"
for %%I in ("%GOACCESS_EXE%") do set "GOACCESS_EXE=%%~fI"

set "GENERATOR_ARGS="
if defined GENERATOR set "GENERATOR_ARGS=%GENERATOR_ARGS% -G "%GENERATOR%""

pushd "%SCRIPT_DIR%" >nul

if "%CTEST_ONLY%"=="1" goto after_build

if "%CLEAN%"=="1" (
    call :run cmake -E remove_directory "%BUILD_DIR%"
    if errorlevel 1 goto fail
    call :run cmake -E remove_directory "%OUT_DIR%"
    if errorlevel 1 goto fail
)

if not "%DRY_RUN%"=="1" if not exist "%CAE_LOGGER_DIR%\cae_loggerConfig.cmake" (
    echo cae_loggerConfig.cmake not found under: "%CAE_LOGGER_DIR%" 1>&2
    goto fail
)
if "%SKIP_E2E%"=="0" if not "%DRY_RUN%"=="1" if not exist "%GOACCESS_EXE%" (
    echo GoAccess executable not found: "%GOACCESS_EXE%" 1>&2
    goto fail
)

if defined CAE_LOGGER_CONFIG (
    call :run cmake %GENERATOR_ARGS% -S "%SCRIPT_DIR%" -B "%BUILD_DIR%" -DCMAKE_BUILD_TYPE="%CONFIG%" -Dcae_logger_DIR="%CAE_LOGGER_DIR%" -DCAE_LOGGER_CONFIG_FILE="%CAE_LOGGER_CONFIG%"
) else (
    call :run cmake %GENERATOR_ARGS% -S "%SCRIPT_DIR%" -B "%BUILD_DIR%" -DCMAKE_BUILD_TYPE="%CONFIG%" -Dcae_logger_DIR="%CAE_LOGGER_DIR%"
)
if errorlevel 1 goto fail

call :run cmake --build "%BUILD_DIR%" --config "%CONFIG%"
if errorlevel 1 goto fail

:after_build

if "%SKIP_CTEST%"=="0" (
    call :run ctest --test-dir "%BUILD_DIR%" --build-config "%CONFIG%" --output-on-failure
    if errorlevel 1 goto fail
)

if "%CTEST_ONLY%"=="1" goto success

set "APP_EXE=%BUILD_DIR%\app_main.exe"
if exist "%BUILD_DIR%\%CONFIG%\app_main.exe" set "APP_EXE=%BUILD_DIR%\%CONFIG%\app_main.exe"
if not exist "%APP_EXE%" if exist "%BUILD_DIR%\app_main" set "APP_EXE=%BUILD_DIR%\app_main"
if not exist "%APP_EXE%" if exist "%BUILD_DIR%\%CONFIG%\app_main" set "APP_EXE=%BUILD_DIR%\%CONFIG%\app_main"

for %%I in ("%APP_EXE%") do set "APP_CONFIG_DIR=%%~dpI"
if "%APP_CONFIG_DIR:~-1%"=="\" set "APP_CONFIG_DIR=%APP_CONFIG_DIR:~0,-1%"
for %%I in ("%GOACCESS_EXE%") do set "GOACCESS_BUILD_DIR=%%~dpI"
if "%GOACCESS_BUILD_DIR:~-1%"=="\" set "GOACCESS_BUILD_DIR=%GOACCESS_BUILD_DIR:~0,-1%"

call :run cmake -DMANIFEST_PATH="%MANIFEST%" -DAPP_EXE="%APP_EXE%" -DAPP_BUILD_DIR="%BUILD_DIR%" -DAPP_CONFIG_DIR="%APP_CONFIG_DIR%" -DCAE_LOGGER_DIR="%CAE_LOGGER_DIR%" -DGOACCESS_EXE="%GOACCESS_EXE%" -DGOACCESS_BUILD_DIR="%GOACCESS_BUILD_DIR%" -DGOACCESS_SOURCE_DIR="%WORKSPACE_DIR%\goaccess" -DLOGS_DIR="%OUT_DIR%\logs" -DREPORTS_DIR="%OUT_DIR%\reports" -DPROFILE_CONFIG="%SCRIPT_DIR%\config\cae_goaccess.conf" -DTEST_CONFIG="%CONFIG%" -P "%SCRIPT_DIR%\cmake\write_cae_manifest.cmake"
if errorlevel 1 goto fail

if "%SKIP_E2E%"=="1" goto success
if "%SKIP_PROBES%"=="1" (
    call :run python -m tools.verify.e2e_verify --manifest "%MANIFEST%" --minimum-lines "%MINIMUM_LINES%" --skip-probes
) else (
    call :run python -m tools.verify.e2e_verify --manifest "%MANIFEST%" --minimum-lines "%MINIMUM_LINES%"
)
if errorlevel 1 goto fail

:success
popd >nul
exit /b 0

:fail
popd >nul
exit /b 1

:run
echo + %*
if "%DRY_RUN%"=="1" exit /b 0
%*
exit /b %ERRORLEVEL%

:usage
echo Usage: build.cmd [options]
echo.
echo Options:
echo   --config ^<Debug^|Release^>       Build configuration ^(default: Debug^)
echo   --build-dir ^<dir^>              Test build directory ^(default: build\^<config^>^)
echo   --out-dir ^<dir^>                Test output directory ^(default: out^)
echo   --manifest ^<file^>              Manifest path ^(default: out\cae_manifest.json^)
echo   --cae-logger-dir ^<dir^>         Installed cae_logger CMake package directory
echo   --cae-logger-config ^<file^>     Installed cae_logger runtime config file
echo   --goaccess-exe ^<file^>          Built GoAccess executable
echo   --generator ^<name^>             CMake generator
echo   --clean                        Remove this project's build/out dirs first
echo   --skip-ctest                   Do not run CTest
echo   --skip-e2e                     Do not run Python e2e verification
echo   --ctest-only                   Run CTest only against an existing test build
echo   --minimum-lines ^<count^>        e2e minimum merged event count
echo   --skip-probes                  Forward to Python e2e verification
echo   --dry-run                      Print commands without running them
echo   --help                         Show this help
exit /b 0

:usage_error
call :usage
exit /b 2
