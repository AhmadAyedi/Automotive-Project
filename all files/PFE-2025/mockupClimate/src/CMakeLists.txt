cmake_minimum_required (VERSION 3.13)

# Définir les flags de compilation C++
set (CMAKE_CXX_FLAGS "-g -std=c++0x")

# Trouver les paquets nécessaires
find_package(vsomeip3 3.4.10 REQUIRED)
find_package(Boost 1.55 COMPONENTS system thread log REQUIRED)
find_package(nlohmann_json 3.9.1 REQUIRED)
# Ajouter les chemins d'inclusion pour MariaDB
include_directories(
    ${Boost_INCLUDE_DIR}
    ${VSOMEIP_INCLUDE_DIRS}
    /usr/include/mariadb
    /usr/include/mariadb/mysql
)

# Ajouter les répertoires de bibliothèque pour MariaDB
link_directories(
    /usr/lib/aarch64-linux-gnu/
)
include_directories(${nlohmann_json_INCLUDE_DIRS})
# Créer l'exécutable et lier les bibliothèques
add_executable(main
    main.cpp
    climates_client.cpp
)
target_link_libraries(main vsomeip3 ${Boost_LIBRARIES} mariadb mysqlcppconn)
target_link_libraries(main nlohmann_json::nlohmann_json)


# Lier avec WiringPi si nécessaire
target_link_libraries(main vsomeip3 wiringPi)