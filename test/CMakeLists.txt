cmake_minimum_required(VERSION 2.8.12)
if(POLICY CMP0048)
    cmake_policy(SET CMP0048 NEW)
endif()
project(cae_logger_test C CXX)

if(CMAKE_VERSION VERSION_LESS "3.1")
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")
    endif()
else()
    set(CMAKE_CXX_STANDARD 11)
    set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()

include(GNUInstallDirs)
include(CTest)

find_package(cae_logger REQUIRED CONFIG)
find_package(Threads REQUIRED)

set(CAE_LOGGER_CONFIG_FILE "" CACHE FILEPATH "Installed cae_logger runtime config file")
if(NOT CAE_LOGGER_CONFIG_FILE)
    if(NOT cae_logger_DIR)
        message(FATAL_ERROR "cae_logger_DIR is required when CAE_LOGGER_CONFIG_FILE is not set.")
    endif()

    get_filename_component(CAE_LOGGER_PACKAGE_DIR "${cae_logger_DIR}" ABSOLUTE)
    get_filename_component(CAE_LOGGER_INSTALL_PREFIX "${CAE_LOGGER_PACKAGE_DIR}/../../.." ABSOLUTE)
    set(CAE_LOGGER_CONFIG_FILE "${CAE_LOGGER_INSTALL_PREFIX}/${CMAKE_INSTALL_BINDIR}/cae_logger_config.ini")
endif()

if(NOT EXISTS "${CAE_LOGGER_CONFIG_FILE}")
    message(FATAL_ERROR "CAE logger runtime config not found: ${CAE_LOGGER_CONFIG_FILE}")
endif()

function(setup_sample_target target_name)
    target_link_libraries(${target_name} cae_logger::cae_logger ${CMAKE_THREAD_LIBS_INIT})

    if(CAE_LOGGER_SYMBOLIC_STACKTRACE AND NOT WIN32 AND (CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang"))
        if(COMMAND target_link_options)
            target_link_options(${target_name} PRIVATE -rdynamic)
        else()
            set_target_properties(${target_name} PROPERTIES LINK_FLAGS "-rdynamic")
        endif()
    endif()

    add_custom_command(TARGET ${target_name} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "$<TARGET_FILE:cae_logger::cae_logger>"
            "$<TARGET_FILE_DIR:${target_name}>"
        COMMENT "Copying cae_logger runtime to ${target_name} directory"
    )

    add_custom_command(TARGET ${target_name} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CAE_LOGGER_CONFIG_FILE}"
            "$<TARGET_FILE_DIR:${target_name}>"
        COMMENT "Copying CAE logger config to ${target_name} directory"
    )

    if(WIN32 AND TARGET spdlog::spdlog)
        get_target_property(SPDLOG_DLL spdlog::spdlog IMPORTED_LOCATION_DEBUG)
        if(NOT SPDLOG_DLL)
            get_target_property(SPDLOG_DLL spdlog::spdlog IMPORTED_LOCATION_RELEASE)
        endif()

        if(SPDLOG_DLL)
            add_custom_command(TARGET ${target_name} POST_BUILD
                COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    "${SPDLOG_DLL}"
                    "$<TARGET_FILE_DIR:${target_name}>"
                COMMENT "Copying spdlog runtime to ${target_name} directory"
            )
        endif()
    endif()
endfunction()

add_executable(app_main
    sample/main.cpp
)

add_executable(cae_postprocess_demo
    sample/cae_postprocess_demo.cpp
)

add_executable(user_document_demo
    sample/user/user_document_demo.cpp
)

add_executable(qt_emit_macro_compat
    sample/qt_emit_macro_compat.cpp
)

add_executable(runtime_config_hot_reload
    sample/runtime_config_update.cpp
)

add_executable(runtime_file_flush
    sample/runtime_file_flush.cpp
)

setup_sample_target(app_main)
setup_sample_target(cae_postprocess_demo)
setup_sample_target(user_document_demo)
setup_sample_target(qt_emit_macro_compat)
setup_sample_target(runtime_config_hot_reload)
setup_sample_target(runtime_file_flush)

file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/logs")

if(BUILD_TESTING)
    add_test(NAME sample_app_main_smoke COMMAND app_main Sample_1)
    set_tests_properties(sample_app_main_smoke PROPERTIES
        WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    )

    add_test(NAME sample_postprocess_smoke COMMAND cae_postprocess_demo Post_1)
    set_tests_properties(sample_postprocess_smoke PROPERTIES
        WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    )

    add_test(NAME sample_user_document_smoke COMMAND user_document_demo DocCase_1)
    set_tests_properties(sample_user_document_smoke PROPERTIES
        WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    )

    add_test(NAME qt_emit_macro_compat_smoke COMMAND qt_emit_macro_compat)
    set_tests_properties(qt_emit_macro_compat_smoke PROPERTIES
        WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    )

    add_test(NAME runtime_config_update_smoke COMMAND runtime_config_hot_reload)
    set_tests_properties(runtime_config_update_smoke PROPERTIES
        WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    )

    add_test(NAME runtime_file_flush_smoke COMMAND runtime_file_flush)
    set_tests_properties(runtime_file_flush_smoke PROPERTIES
        WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    )
endif()
