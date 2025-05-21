#ifndef CLIMATES_CLIENT_H
#define CLIMATES_CLIENT_H

#include <vsomeip/vsomeip.hpp>
#include <iostream>
#include <vector>
#include <mutex>
#include <condition_variable>
#include <fstream>
#include <csignal>
#include <chrono>
#include <iomanip>
#include <ctime>

// Identifiants du service
#define SAMPLE_SERVICE_ID       0x4796
#define SAMPLE_INSTANCE_ID      0x4786

// Identifiants des événements
#define CLIMATE_EVENTGROUP_ID       0x0523
#define CLASSIC_CLIMATE_EVENT_ID    0x6E
#define SMART_CLIMATE_EVENT_ID      0x6F

class ClimateClient {
public:
    ClimateClient();
    ~ClimateClient();

    bool init();
    void start();
    void stop();

private:
    std::shared_ptr<vsomeip::application> app_;
    std::mutex mutex_;
    std::condition_variable condition_;
    bool service_available_;
    bool running_;
    std::ofstream log_file_;

    // Méthodes privées
    std::string get_current_timestamp();
    void log_message(const std::string& message);
    void log_packet(const std::shared_ptr<vsomeip::message>& _response, const std::string& payload_str);
    
    // Handlers
    void on_message(const std::shared_ptr<vsomeip::message> &_response);
    void on_availability(vsomeip::service_t service, vsomeip::instance_t instance, bool is_available);
    static void signal_handler(int signal);

    // Callbacks
    void classic_climate(const std::string &state);
    void smart_climate(const std::string &state);
};

#endif // CLIMATE_CLIENT_H