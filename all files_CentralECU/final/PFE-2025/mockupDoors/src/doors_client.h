#ifndef DOORS_CLIENT_H
#define DOORS_CLIENT_H

#include <memory>
#include <string>
#include <vsomeip/vsomeip.hpp>
#include <mutex>
#include <condition_variable>
#include <sstream>
#include <iomanip>
#include <fstream>
#include <chrono>

// Définition des IDs
#define SAMPLE_SERVICE_ID 0x1234
#define SAMPLE_INSTANCE_ID 0x5678
#define DOORS_EVENTGROUP_ID 0x0654
#define FRONT_RIGHT_DOOR_EVENT_ID 0x11D
#define REAR_RIGHT_DOOR_EVENT_ID 0x11E
#define FRONT_LEFT_DOOR_EVENT_ID 0x11F
#define REAR_LEFT_DOOR_EVENT_ID 0x120
#define KEY_EVENT_ID 0x64

class DoorsClient {
public:
    DoorsClient();
    ~DoorsClient();

    bool init();
    void start();
    void stop();

private:
    std::shared_ptr<vsomeip::application> app_;
    std::mutex mutex_;
    std::condition_variable condition_;
    bool service_available_;
    const std::string log_file_path = "/home/pi/vsomeip/PFE-2025/mockupDoors/src/doors_log.txt";
    
    // Gestion des callbacks
    void on_message(const std::shared_ptr<vsomeip::message> &_response);
    void on_availability(vsomeip::service_t _service, vsomeip::instance_t _instance, bool _is_available);
    
    // Actions sur les portes et clé
    void front_right_door(const std::string &state);
    void rear_right_door(const std::string &state);
    void front_left_door(const std::string &state);
    void rear_left_door(const std::string &state);
    void key_door(const std::string &state);
    
    // Helper pour le logging
    std::string message_to_string(const std::shared_ptr<vsomeip::message> &_response) const;
    void log_to_file(const std::shared_ptr<vsomeip::message> &_response, const std::string& action_message);
    std::string get_current_timestamp();
};

#endif // DOORS_CLIENT_H