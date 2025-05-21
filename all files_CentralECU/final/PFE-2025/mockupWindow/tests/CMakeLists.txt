cmake_minimum_required(VERSION 3.13)
project(windows_client_tests)

# GTest
include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/release-1.12.1.zip
)
FetchContent_MakeAvailable(googletest)

# Activer les tests
enable_testing()

# Inclure le dossier contenant windows_client.h et d'autres en-têtes nécessaires
include_directories(${CMAKE_SOURCE_DIR}/src)

# Ajouter le test
add_executable(test_windows_client
    test_windows_client.cpp
    ../src/windows_client.cpp
    ../src/windows_client.h
)

# Lier avec GTest, pthread et vsomeip (si besoin)
target_link_libraries(test_windows_client
    gtest
    gtest_main
    pthread
)

add_test(NAME WindowsClientTests COMMAND test_windows_client)
