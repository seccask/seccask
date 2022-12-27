cmake_minimum_required(VERSION 3.17)
project(seccask2)

set(CMAKE_CXX_STANDARD 17)

# set(BOOST_USE_ASAN TRUE)
# set(ASAN_SYMBOLIZER_PATH /usr/bin/llvm-symbolizer-10)
# add_compile_options(-fsanitize=address)
# add_link_options(-fsanitize=address)
include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

include_directories(include/)

set(Python3_ROOT_DIR /home/mlcask/sgx/lib/cpython-3.9.13-install)
find_package(Python3 3.9 EXACT COMPONENTS Development)

find_library(USTORE_LIBS 
      NAMES ustore
      PATHS extern/ustore_release/lib)

add_executable(seccask
    csrc/encfs.cc
    csrc/ratls.cc
    csrc/message.cc
    csrc/msg_handler.cc
    csrc/worker.cc
    csrc/coordinator.cc
    csrc/main.cc
    csrc/ustore.cc
)
set_property(TARGET seccask PROPERTY ENABLE_EXPORTS ON)
target_compile_definitions(seccask PRIVATE BOOST_USE_VALGRIND)
target_include_directories(seccask
    PRIVATE
    ${Python3_INCLUDE_DIRS}
    extern/ustore_release/include
    extern/include
)
target_link_libraries(seccask
    ${CONAN_LIBS}
    ${Python3_LIBRARIES}
    ${USTORE_LIBS}
    dl
)