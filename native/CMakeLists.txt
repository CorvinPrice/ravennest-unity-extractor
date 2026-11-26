cmake_minimum_required(VERSION 3.22)
project(raven_texture2ddecoder LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(T2D_DIR ${CMAKE_CURRENT_SOURCE_DIR}/third_party/texture2ddecoder/src/Texture2DDecoder)

add_library(raven_texture2ddecoder SHARED
    raven_texture2ddecoder.cpp
    ${T2D_DIR}/astc.cpp
    ${T2D_DIR}/atc.cpp
    ${T2D_DIR}/bcn.cpp
    ${T2D_DIR}/crunch.cpp
    ${T2D_DIR}/etc.cpp
    ${T2D_DIR}/pvrtc.cpp
    ${T2D_DIR}/unitycrunch.cpp
)

target_include_directories(raven_texture2ddecoder PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${T2D_DIR}
)

target_compile_options(raven_texture2ddecoder PRIVATE
    -O2
    -fvisibility=hidden
    -ffunction-sections
    -fdata-sections
)

if(ANDROID)
    target_link_options(raven_texture2ddecoder PRIVATE -Wl,--gc-sections)
endif()
