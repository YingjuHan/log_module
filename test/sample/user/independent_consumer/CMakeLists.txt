cmake_minimum_required(VERSION 2.8.12)
if(POLICY CMP0048)
    cmake_policy(SET CMP0048 NEW)
endif()
project(cae_logger_independent_consumer CXX)

if(CMAKE_VERSION VERSION_LESS "3.1")
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")
    endif()
else()
    set(CMAKE_CXX_STANDARD 11)
    set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()

find_package(cae_logger REQUIRED CONFIG)

add_executable(independent_consumer
    main.cpp
)

target_link_libraries(independent_consumer cae_logger::cae_logger)

add_custom_command(TARGET independent_consumer POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "$<TARGET_FILE:cae_logger::cae_logger>"
        "$<TARGET_FILE_DIR:independent_consumer>"
    COMMENT "Copying cae_logger runtime to independent_consumer directory"
)

if(WIN32 AND TARGET spdlog::spdlog)
    get_target_property(SPDLOG_DLL spdlog::spdlog IMPORTED_LOCATION_DEBUG)
    if(NOT SPDLOG_DLL)
        get_target_property(SPDLOG_DLL spdlog::spdlog IMPORTED_LOCATION_RELEASE)
    endif()

    if(SPDLOG_DLL)
        add_custom_command(TARGET independent_consumer POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${SPDLOG_DLL}"
                "$<TARGET_FILE_DIR:independent_consumer>"
            COMMENT "Copying spdlog runtime to independent_consumer directory"
        )
    endif()
endif()
