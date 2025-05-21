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

    // Main loop - pourrait �tre remplac� par une logique plus sophistiqu�e
    while (true) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    return 0;
}