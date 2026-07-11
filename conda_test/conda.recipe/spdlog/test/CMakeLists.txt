cmake_minimum_required(VERSION 3.15)
project(spdlog_recipe_test LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(spdlog 1.11.0 CONFIG REQUIRED)

add_executable(spdlog_recipe_consumer main.cpp)
target_link_libraries(spdlog_recipe_consumer PRIVATE spdlog::spdlog_header_only)
