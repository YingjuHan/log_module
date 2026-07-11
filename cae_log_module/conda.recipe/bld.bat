@echo on
setlocal EnableExtensions

cmake -S . -B build -G "MinGW Makefiles" ^
    -DCMAKE_INSTALL_PREFIX="%LIBRARY_PREFIX%" ^
    -DCMAKE_PREFIX_PATH="%LIBRARY_PREFIX%" ^
    -DBOOST_ROOT="%LIBRARY_PREFIX%" ^
    -DCAE_LOGGER_BUILD_DOCS=OFF ^
    -DCAE_LOGGER_INSTALL_DOCS=OFF ^
    -DCAE_LOGGER_INSTALL_TEST_PROJECT=OFF ^
    -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 exit /b 1

cmake --build build --config Release --parallel
if errorlevel 1 exit /b 1

cmake --install build --config Release
if errorlevel 1 exit /b 1
