#ifndef VEHICLE_CLIENT_H
#define VEHICLE_CLIENT_H

#include <memory>
#include <string>
#include <vsomeip/vsomeip.hpp>
#include <mutex>
#include <condition_variable>
#include <sstream>
#include <iomanip>
#include <fstream>

// Définition des IDs pour Lights
#define LIGHTS_SERVICE_ID 0x1234
#define LIGHTS_INSTANCE_ID 0x5678
#define LIGHTS_EVENTGROUP_ID 0x0321
#define LOW_BEAM_HEADLIGHT_EVENT_ID 0x0123
#define HAZARD_LIGHT_EVENT_ID 0x0124
#define RIGHT_TURN_EVENT_ID 0x0125
#define LEFT_TURN_EVENT_ID 0x0126
#define HIGH_BEAM_HEADLIGHT_EVENT_ID 0x0127
#define PARKING_LEFT_EVENT_ID 0x0128
#define PARKING_RIGHT_EVENT_ID 0x0129

// Définition des IDs pour Doors
#define DOORS_SERVICE_ID 0x1235
#define DOORS_INSTANCE_ID 0x5679
#define DOORS_EVENTGROUP_ID 0x0654
#define FRONT_RIGHT_DOOR_EVENT_ID 0x11D
#define REAR_RIGHT_DOOR_EVENT_ID 0x11E
#define FRONT_LEFT_DOOR_EVENT_ID 0x012F
#define REAR_LEFT_DOOR_EVENT_ID 0x120
#define KEY_EVENT_ID 0x064

class VehicleClient {
public:
    VehicleClient();
    ~VehicleClient();

    bool init();
    void start();
    void stop();

private:
    std::shared_ptr<vsomeip::application> app_;
    std::mutex mutex_;
    std::condition_variable condition_;
    bool lights_service_available_;
    bool doors_service_available_;
    
    const std::string lights_log_path = "/home/pi/vsomeip/PFE-2025/vehicle_client/logs/lights_log.txt";
    const std::string doors_log_path = "/home/pi/vsomeip/PFE-2025/vehicle_client/logs/doors_log.txt";
    
    // Callbacks
    void on_message(const std::shared_ptr<vsomeip::message> &_response);
    void on_availability(vsomeip::service_t _service, vsomeip::instance_t _instance, bool _is_available);
    
    // Handlers pour les lumières
    void handle_lights_events(const std::shared_ptr<vsomeip::message> &_response);
    void handle_doors_events(const std::shared_ptr<vsomeip::message> &_response);
    
    // Logging
    void log_to_file(const std::string &file_path, const std::shared_ptr<vsomeip::message> &_response, const std::string& action_message);
    std::string message_to_string(const std::shared_ptr<vsomeip::message> &_response) const;
    
    // Initialisation des services
    void init_lights_service();
    void init_doors_service();
};

#endif // VEHICLE_CLIENT_H