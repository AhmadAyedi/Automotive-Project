#ifndef WINDOWS_CLIENT_H
#define WINDOWS_CLIENT_H

#include <memory>
#include <string>
#include <iostream>  // Ajouté pour l'output
#include <vsomeip/vsomeip.hpp>
#include <mutex>
#include <condition_variable>
#include <sstream>
#include <iomanip>
#include <fstream>

// Définition des IDs
#define SAMPLE_SERVICE_ID 0x0EC8
#define SAMPLE_INSTANCE_ID 0x5670
#define WINDOW_EVENTGROUP_ID 0x0708
#define DRIVER_WINDOW_EVENT_ID 0x0186
#define REAR_DRIVER_WINDOW_EVENT_ID 0x0187
#define PASSENGER_WINDOW_EVENT_ID 0x0188
#define REAR_PASSENGER_EVENT_ID 0x0189
#define SAFETY_EVENT_ID 0x018A

class WindowsClient {
public:
    WindowsClient() : service_available_(false) {}
    ~WindowsClient() {}

    bool init() {
        // Simulation d'initialisation
        std::cout << "Initialization complete.\n";
        return true;
    }

    void start() {
        // Simulation du démarrage
        std::cout << "Client started.\n";
    }

    void stop() {
        // Simulation de l'arrêt
        std::cout << "Client stopped.\n";
    }

    void driver_window(const std::string &state) {
        // Simulation de l'action sur la fenêtre du conducteur
        std::cout << "Driver Window | Status: " << state << std::endl;
    }

private:
    std::shared_ptr<vsomeip::application> app_;
    std::mutex mutex_;
    std::condition_variable condition_;
    bool service_available_;
    const std::string log_file_path = "/home/pi/vsomeip/PFE-2025/mockupWindow/src/windows_log.txt";
};

#endif // WINDOWS_CLIENT_H
