@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "CONFIG=Debug"
set "BUILD_DIR="
set "INSTALL_PREFIX="
set "GENERATOR="
set "GENERATOR_PLATFORM="
set "GENERATOR_TOOLSET="
set "CLEAN=0"
set "DRY_RUN=0"

:parse
if "%~1"=="" goto after_parse
if /I "%~1"=="--config" set "CONFIG=%~2" & shift & shift & goto parse
if /I "%~1"=="--build-dir" set "BUILD_DIR=%~2" & shift & shift & goto parse
if /I "%~1"=="--install-prefix" set "INSTALL_PREFIX=%~2" & shift & shift & goto parse
if /I "%~1"=="--generator" set "GENERATOR=%~2" & shift & shift & goto parse
if /I "%~1"=="--generator-platform" set "GENERATOR_PLATFORM=%~2" & shift & shift & goto parse
if /I "%~1"=="--generator-toolset" set "GENERATOR_TOOLSET=%~2" & shift & shift & goto parse
if /I "%~1"=="--clean" set "CLEAN=1" & shift & goto parse
if /I "%~1"=="--dry-run" set "DRY_RUN=1" & shift & goto parse
if /I "%~1"=="--help" goto usage
echo Unknown option: %~1 1>&2
goto usage_error

:after_parse
if not defined BUILD_DIR set "BUILD_DIR=%SCRIPT_DIR%\build\%CONFIG%"
if not defined INSTALL_PREFIX set "INSTALL_PREFIX=%SCRIPT_DIR%\install\%CONFIG%"
set "ENABLE_DEBUG=OFF"
if /I "%CONFIG%"=="Debug" set "ENABLE_DEBUG=ON"

set "GENERATOR_ARGS="
if defined GENERATOR set "GENERATOR_ARGS=%GENERATOR_ARGS% -G "%GENERATOR%""
if defined GENERATOR_PLATFORM set "GENERATOR_ARGS=%GENERATOR_ARGS% -A "%GENERATOR_PLATFORM%""
if defined GENERATOR_TOOLSET set "GENERATOR_ARGS=%GENERATOR_ARGS% -T "%GENERATOR_TOOLSET%""

if "%CLEAN%"=="1" (
    call :run cmake -E rm -rf "%BUILD_DIR%" "%INSTALL_PREFIX%"
    if errorlevel 1 exit /b 1
)

call :run cmake %GENERATOR_ARGS% -S "%SCRIPT_DIR%" -B "%BUILD_DIR%" -DCMAKE_BUILD_TYPE="%CONFIG%" -DCMAKE_INSTALL_PREFIX="%INSTALL_PREFIX%" -DENABLE_DEBUG="%ENABLE_DEBUG%" -DENABLE_NCURSES=ON -DWITH_ZLIB=ON -DENABLE_NLS=OFF -DGOACCESS_ALLOW_SYSTEM_DEPS=OFF -DGOACCESS_REGENERATE_EMBEDDED_RESOURCES=OFF -DGETTEXT_SRC_DIR="%SCRIPT_DIR%\thirdparty\gettext" -DZLIB_SRC_DIR="%SCRIPT_DIR%\thirdparty\zlib" -DPDCURSES_SRC_DIR="%SCRIPT_DIR%\thirdparty\PDCurses"
if errorlevel 1 exit /b 1

call :run cmake --build "%BUILD_DIR%" --config "%CONFIG%" --target goaccess
if errorlevel 1 exit /b 1

call :run cmake --install "%BUILD_DIR%" --config "%CONFIG%" --prefix "%INSTALL_PREFIX%"
if errorlevel 1 exit /b 1

set "GOACCESS_EXE=%BUILD_DIR%\goaccess.exe"
if exist "%BUILD_DIR%\%CONFIG%\goaccess.exe" set "GOACCESS_EXE=%BUILD_DIR%\%CONFIG%\goaccess.exe"
if not exist "%GOACCESS_EXE%" if exist "%INSTALL_PREFIX%\bin\goaccess.exe" set "GOACCESS_EXE=%INSTALL_PREFIX%\bin\goaccess.exe"

if not "%DRY_RUN%"=="1" if not exist "%BUILD_DIR%\CMakeCache.txt" (
    echo GoAccess CMake cache not found: "%BUILD_DIR%\CMakeCache.txt" 1>&2
    exit /b 1
)
if not "%DRY_RUN%"=="1" if not exist "%GOACCESS_EXE%" (
    echo GoAccess executable not found: "%GOACCESS_EXE%" 1>&2
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
echo   --generator ^<name^>             CMake generator
echo   --generator-platform ^<name^>    CMake -A value
echo   --generator-toolset ^<name^>     CMake -T value
echo   --clean                        Remove this project's build/install dirs first
echo   --dry-run                      Print commands without running them
echo   --help                         Show this help
exit /b 0

:usage_error
call :usage
exit /b 2
