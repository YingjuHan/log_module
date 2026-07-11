@echo off
setlocal EnableDelayedExpansion

echo ==========================
echo Building Boost 1.68.0
echo ==========================

set PATH=%BUILD_PREFIX%\Library\mingw-w64\bin;%PATH%
set PATH=%BUILD_PREFIX%\mingw-w64\bin;%PATH%

set PREFIX=%LIBRARY_PREFIX%


call bootstrap.bat gcc


set TOOLSET=gcc


b2 ^
  -j%CPU_COUNT% ^
  --without-test ^
  toolset=%TOOLSET% ^
  variant=release ^
  threading=multi ^
  link=shared ^
  runtime-link=shared ^
  address-model=64 ^
  --prefix=%PREFIX% ^
  install


if errorlevel 1 (
    echo Boost build failed
    exit /b 1
)


echo ==========================
echo Boost installation finished
echo ==========================