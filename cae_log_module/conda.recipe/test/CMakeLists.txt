cmake_minimum_required(VERSION 3.15)
project(cae_logger_conda_consumer CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(cae_logger REQUIRED CONFIG)

add_executable(cae_logger_conda_consumer main.cpp)
target_link_libraries(cae_logger_conda_consumer PRIVATE cae_logger::cae_logger)
