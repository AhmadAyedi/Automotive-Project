#include "doors_client.h"
#include <iostream>
#include <thread>
#include <chrono>

int main() {
    DoorsClient client;
    
    if (!client.init()) {
        return -1;
    }

    client.start();

    // Main loop - pourrait être remplacé par une logique plus sophistiquée
    while (true) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    return 0;
}