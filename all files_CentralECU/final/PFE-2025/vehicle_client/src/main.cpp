#include "vehicle_client.h"
#include <iostream>
#include <csignal>
#include <atomic>
#include <thread>
#include <chrono>

std::unique_ptr<VehicleClient> vehicle_client;
std::atomic<bool> running{true};

void signal_handler(int signal) {
    std::cout << "Signal " << signal << " received, shutting down..." << std::endl;
    running = false;
    if (vehicle_client) {
        vehicle_client->stop();
    }
}

int main() {
    // Configuration des handlers de signal
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    std::cout << "Starting Vehicle Client..." << std::endl;
    
    // Remplacement de std::make_unique pour C++11
    vehicle_client.reset(new VehicleClient());
    
    if (!vehicle_client->init()) {
        std::cerr << "Failed to initialize Vehicle Client!" << std::endl;
        return 1;
    }
    
    vehicle_client->start();
    
    std::cout << "Vehicle Client started. Waiting for messages..." << std::endl;
    
    // Boucle principale
    while (running) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    
    std::cout << "Vehicle Client stopped successfully." << std::endl;
    return 0;
}