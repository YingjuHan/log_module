@echo on
if not exist "%LIBRARY_PREFIX%\include" mkdir "%LIBRARY_PREFIX%\include"
if errorlevel 1 exit /b 1
xcopy /E /I /Y include\spdlog "%LIBRARY_PREFIX%\include\spdlog"
if errorlevel 1 exit /b 1

set "CMAKE_PACKAGE_DIR=%LIBRARY_PREFIX%\lib\cmake\spdlog"
if not exist "%CMAKE_PACKAGE_DIR%" mkdir "%CMAKE_PACKAGE_DIR%"
if errorlevel 1 exit /b 1

> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo include^(CMakeFindDependencyMacro^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo find_dependency^(fmt 9.1.0 CONFIG^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo if^(UNIX^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo   find_dependency^(Threads^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo endif^(^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo.
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo get_filename_component^(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo.
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo if^(NOT TARGET spdlog::spdlog_header_only^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo   add_library^(spdlog::spdlog_header_only INTERFACE IMPORTED^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo   set_target_properties^(spdlog::spdlog_header_only PROPERTIES
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo     INTERFACE_INCLUDE_DIRECTORIES "${PACKAGE_PREFIX_DIR}/include"
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo     INTERFACE_COMPILE_DEFINITIONS "SPDLOG_FMT_EXTERNAL"
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo     INTERFACE_LINK_LIBRARIES "fmt::fmt-header-only"
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo   ^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo   if^(UNIX^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo     set_property^(TARGET spdlog::spdlog_header_only APPEND PROPERTY
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo       INTERFACE_LINK_LIBRARIES Threads::Threads^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo   endif^(^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfig.cmake" echo endif^(^)

> "%CMAKE_PACKAGE_DIR%\spdlogConfigVersion.cmake" echo set^(PACKAGE_VERSION "1.11.0"^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfigVersion.cmake" echo set^(PACKAGE_VERSION_COMPATIBLE FALSE^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfigVersion.cmake" echo set^(PACKAGE_VERSION_EXACT FALSE^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfigVersion.cmake" echo.
>> "%CMAKE_PACKAGE_DIR%\spdlogConfigVersion.cmake" echo if^("${PACKAGE_FIND_VERSION_MAJOR}" STREQUAL "1"^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfigVersion.cmake" echo   if^(NOT "${PACKAGE_FIND_VERSION}" VERSION_GREATER "${PACKAGE_VERSION}"^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfigVersion.cmake" echo     set^(PACKAGE_VERSION_COMPATIBLE TRUE^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfigVersion.cmake" echo     if^("${PACKAGE_FIND_VERSION}" VERSION_EQUAL "${PACKAGE_VERSION}"^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfigVersion.cmake" echo       set^(PACKAGE_VERSION_EXACT TRUE^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfigVersion.cmake" echo     endif^(^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfigVersion.cmake" echo   endif^(^)
>> "%CMAKE_PACKAGE_DIR%\spdlogConfigVersion.cmake" echo endif^(^)
