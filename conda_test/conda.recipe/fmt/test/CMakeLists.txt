cmake_minimum_required(VERSION 3.15)
project(fmt_recipe_test LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(fmt 9.1.0 CONFIG REQUIRED)

add_executable(fmt_recipe_consumer main.cpp)
target_link_libraries(fmt_recipe_consumer PRIVATE fmt::fmt-header-only)
