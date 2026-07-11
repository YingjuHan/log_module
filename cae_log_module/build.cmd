@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "CONFIG=Debug"
set "BUILD_DIR="
set "INSTALL_PREFIX="
set "GENERATOR="
set "PREFIX_PATH=%CAE_LOGGER_PREFIX_PATH%"
set "CLEAN=0"
set "DRY_RUN=0"

:parse
if "%~1"=="" goto after_parse
if /I "%~1"=="--config" set "CONFIG=%~2" & shift & shift & goto parse
if /I "%~1"=="--build-dir" set "BUILD_DIR=%~2" & shift & shift & goto parse
if /I "%~1"=="--install-prefix" set "INSTALL_PREFIX=%~2" & shift & shift & goto parse
if /I "%~1"=="--generator" set "GENERATOR=%~2" & shift & shift & goto parse
if /I "%~1"=="--prefix-path" set "PREFIX_PATH=%~2" & shift & shift & goto parse
if /I "%~1"=="--clean" set "CLEAN=1" & shift & goto parse
if /I "%~1"=="--dry-run" set "DRY_RUN=1" & shift & goto parse
if /I "%~1"=="--help" goto usage
echo Unknown option: %~1 1>&2
goto usage_error

:after_parse
if not defined BUILD_DIR set "BUILD_DIR=%SCRIPT_DIR%\build\%CONFIG%"
if not defined INSTALL_PREFIX set "INSTALL_PREFIX=%SCRIPT_DIR%\install\%CONFIG%"

set "GENERATOR_ARGS="
if defined GENERATOR set "GENERATOR_ARGS=%GENERATOR_ARGS% -G "%GENERATOR%""
set "PREFIX_PATH_ARG="
if defined PREFIX_PATH set "PREFIX_PATH_ARG=-DCMAKE_PREFIX_PATH=%PREFIX_PATH%"

if "%CLEAN%"=="1" (
    call :run cmake -E remove_directory "%BUILD_DIR%"
    if errorlevel 1 exit /b 1
    call :run cmake -E remove_directory "%INSTALL_PREFIX%"
    if errorlevel 1 exit /b 1
)

call :run cmake %GENERATOR_ARGS% -S "%SCRIPT_DIR%" -B "%BUILD_DIR%" -DCMAKE_BUILD_TYPE="%CONFIG%" %PREFIX_PATH_ARG%
if errorlevel 1 exit /b 1

call :run cmake --build "%BUILD_DIR%" --config "%CONFIG%" --target cae_logger -j8
if errorlevel 1 exit /b 1

call :run cmake --install "%BUILD_DIR%" --config "%CONFIG%" --prefix "%INSTALL_PREFIX%"
if errorlevel 1 exit /b 1

set "PACKAGE_CONFIG=%INSTALL_PREFIX%\lib\cmake\cae_logger\cae_loggerConfig.cmake"
if not "%DRY_RUN%"=="1" if not exist "%PACKAGE_CONFIG%" (
    echo cae_logger package config not found: "%PACKAGE_CONFIG%" 1>&2
    exit /b 1
)

exit /b 0

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
echo   --build-dir ^<dir^>              Build directory ^(default: build\^<config^>^)
echo   --install-prefix ^<dir^>         Install prefix ^(default: install\^<config^>^)
echo   --generator ^<name^>             CMake generator, for example "MinGW Makefiles"
echo   --prefix-path ^<path^>          CMake dependency prefix ^(or set CAE_LOGGER_PREFIX_PATH^)
echo   --clean                        Remove this project's build/install dirs first
echo   --dry-run                      Print commands without running them
echo   --help                         Show this help
exit /b 0

:usage_error
call :usage
exit /b 2
