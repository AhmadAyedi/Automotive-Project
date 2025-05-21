#include "climates_client.h"
#include <iostream>
#include <chrono>
#include <thread>

int main() {
    ClimateClient client;

    if (!client.init()) {
        return -1;
    }

    client.start();

    // Boucle principale
    while (true) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    return 0;
}