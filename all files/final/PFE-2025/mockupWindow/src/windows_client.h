#ifndef WINDOWS_CLIENT_H
#define WINDOWS_CLIENT_H

#include <memory>
#include <string>
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
    WindowsClient();
    ~WindowsClient();

    bool init();
    void start();
    void stop();

    // === Ces méthodes sont maintenant publiques pour les tests ===
    void driver_window(const std::string &state);
    void rear_driver_window(const std::string &state);
    void passenger_window(const std::string &state);
    void rear_passenger_window(const std::string &state);
    void safety_window(const std::string &state);

private:
    std::shared_ptr<vsomeip::application> app_;
    std::mutex mutex_;
    std::condition_variable condition_;
    bool service_available_;
    const std::string log_file_path = "/home/pi/vsomeip/PFE-2025/mockupWindow/src/windows_log.txt";

    // Gestion des callbacks
    void on_message(const std::shared_ptr<vsomeip::message> &response);
    void on_availability(vsomeip::service_t service, vsomeip::instance_t instance, bool is_available);

    // Logging
    std::string message_to_string(const std::shared_ptr<vsomeip::message> &_response) const;
    void log_to_file(const std::shared_ptr<vsomeip::message> &_response, const std::string& action_message);
    std::string get_current_timestamp();
};

#endif // WINDOWS_CLIENT_H