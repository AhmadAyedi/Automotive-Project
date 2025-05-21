#include "windows_client.h"
#include <iostream>
#include <thread>
#include <chrono>

int main() {
    WindowsClient client;
    
    if (!client.init()) {
        return -1;
    }

    client.start();

    // Boucle principale (pourrait être remplacée par une logique plus sophistiquée)
    while (true) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    return 0;
}