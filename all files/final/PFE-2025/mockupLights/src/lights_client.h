#ifndef LIGHTS_CLIENT_H
#define LIGHTS_CLIENT_H

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
#define LIGHTS_EVENTGROUP_ID 0x0321
#define LOW_BEAM_HEADLIGHT_EVENT_ID 0x0123
#define HAZARD_LIGHT_EVENT_ID 0x0124
#define RIGHT_TURN_EVENT_ID 0x0125
#define LEFT_TURN_EVENT_ID 0x0126
#define HIGH_BEAM_HEADLIGHT_EVENT_ID 0x0127
#define PARKING_LEFT_EVENT_ID 0x0128
#define PARKING_RIGHT_EVENT_ID 0x0129

class LightsClient {
public:
    LightsClient();
    ~LightsClient();

    bool init();
    void start();
    void stop();

private:
    std::shared_ptr<vsomeip::application> app_;
    std::mutex mutex_;
    std::condition_variable condition_;
    bool service_available_;
    
    // Gestion des callbacks
    void on_message(const std::shared_ptr<vsomeip::message> &_response);
    void on_availability(vsomeip::service_t _service, vsomeip::instance_t _instance, bool _is_available);
    
    // Actions sur les lumières
    void turn_on_low_beam_headlights(const std::string &state);
    void turn_on_hazard_lights(const std::string &state);
    void turn_on_right_turn_signal(const std::string &state);
    void turn_on_left_turn_signal(const std::string &state);
    void turn_on_high_beam_headlights(const std::string &state);
    void turn_on_parking_left_signal(const std::string &state);
    void turn_on_parking_right_signal(const std::string &state);
    
    // Méthode pour enregistrer les données dans un fichier
    void log_to_file(const std::shared_ptr<vsomeip::message> &_response, const std::string& action_message);
    
    // Helper pour le logging
    std::string message_to_string(const std::shared_ptr<vsomeip::message> &_response) const;
    std::string get_current_timestamp();
    
    // Chemin du fichier de log
    const std::string log_file_path = "/home/pi/vsomeip/PFE-2025/mockupLights/src/lights_log.txt";
};

#endif // LIGHTS_CLIENT_H