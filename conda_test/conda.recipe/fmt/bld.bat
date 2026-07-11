@echo on
if not exist "%LIBRARY_PREFIX%\include" mkdir "%LIBRARY_PREFIX%\include"
if errorlevel 1 exit /b 1
xcopy /E /I /Y include\fmt "%LIBRARY_PREFIX%\include\fmt"
if errorlevel 1 exit /b 1

set "CMAKE_PACKAGE_DIR=%LIBRARY_PREFIX%\lib\cmake\fmt"
if not exist "%CMAKE_PACKAGE_DIR%" mkdir "%CMAKE_PACKAGE_DIR%"
if errorlevel 1 exit /b 1

> "%CMAKE_PACKAGE_DIR%\fmtConfig.cmake" echo get_filename_component^(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfig.cmake" echo.
>> "%CMAKE_PACKAGE_DIR%\fmtConfig.cmake" echo if^(NOT TARGET fmt::fmt-header-only^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfig.cmake" echo   add_library^(fmt::fmt-header-only INTERFACE IMPORTED^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfig.cmake" echo   set_target_properties^(fmt::fmt-header-only PROPERTIES
>> "%CMAKE_PACKAGE_DIR%\fmtConfig.cmake" echo     INTERFACE_INCLUDE_DIRECTORIES "${PACKAGE_PREFIX_DIR}/include"
>> "%CMAKE_PACKAGE_DIR%\fmtConfig.cmake" echo     INTERFACE_COMPILE_DEFINITIONS "FMT_HEADER_ONLY=1"
>> "%CMAKE_PACKAGE_DIR%\fmtConfig.cmake" echo   ^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfig.cmake" echo endif^(^)

> "%CMAKE_PACKAGE_DIR%\fmtConfigVersion.cmake" echo set^(PACKAGE_VERSION "9.1.0"^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfigVersion.cmake" echo set^(PACKAGE_VERSION_COMPATIBLE FALSE^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfigVersion.cmake" echo set^(PACKAGE_VERSION_EXACT FALSE^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfigVersion.cmake" echo.
>> "%CMAKE_PACKAGE_DIR%\fmtConfigVersion.cmake" echo if^("${PACKAGE_FIND_VERSION_MAJOR}" STREQUAL "9"^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfigVersion.cmake" echo   if^(NOT "${PACKAGE_FIND_VERSION}" VERSION_GREATER "${PACKAGE_VERSION}"^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfigVersion.cmake" echo     set^(PACKAGE_VERSION_COMPATIBLE TRUE^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfigVersion.cmake" echo     if^("${PACKAGE_FIND_VERSION}" VERSION_EQUAL "${PACKAGE_VERSION}"^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfigVersion.cmake" echo       set^(PACKAGE_VERSION_EXACT TRUE^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfigVersion.cmake" echo     endif^(^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfigVersion.cmake" echo   endif^(^)
>> "%CMAKE_PACKAGE_DIR%\fmtConfigVersion.cmake" echo endif^(^)
