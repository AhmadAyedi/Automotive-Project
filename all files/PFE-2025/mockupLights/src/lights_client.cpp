#include "lights_client.h"
#include <iostream>
#include <ctime>    // Pour obtenir l'heure actuelle
#include <iomanip>  // Pour formater l'heure

LightsClient::LightsClient() 
    : app_(vsomeip::runtime::get()->create_application("LIGHTS")),
      service_available_(false) {
}

LightsClient::~LightsClient() {
    stop();
}

bool LightsClient::init() {
    if (!app_->init()) {
        std::cerr << "CLIENT: Failed to initialize vsomeip application!" << std::endl;
        return false;
    }

    app_->register_availability_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
        [this](vsomeip::service_t s, vsomeip::instance_t i, bool a) { 
            this->on_availability(s, i, a); 
        });
    
    auto message_handler = [this](const std::shared_ptr<vsomeip::message> &m) {
        this->on_message(m);
    };

    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 LOW_BEAM_HEADLIGHT_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 HAZARD_LIGHT_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 RIGHT_TURN_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 LEFT_TURN_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 HIGH_BEAM_HEADLIGHT_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 PARKING_LEFT_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 PARKING_RIGHT_EVENT_ID, message_handler);
    
    app_->request_service(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID);
    
    return true;
}

void LightsClient::start() {
    app_->start();
}

void LightsClient::stop() {
    app_->stop();
}

void LightsClient::on_message(const std::shared_ptr<vsomeip::message> &_response) {
    std::cout << message_to_string(_response) << std::endl;

    std::shared_ptr<vsomeip::payload> its_payload = _response->get_payload();
    std::string received_message(reinterpret_cast<char *>(its_payload->get_data()), 
                               its_payload->get_length());

    std::string action_message;
    
    switch (_response->get_method()) {
        case LOW_BEAM_HEADLIGHT_EVENT_ID:
            action_message = "Low Beam Headlights | " + received_message;
            turn_on_low_beam_headlights(received_message);
            break;
        case HAZARD_LIGHT_EVENT_ID:
            action_message = "Hazard Lights | " + received_message;
            turn_on_hazard_lights(received_message);
            break;
        case RIGHT_TURN_EVENT_ID:
            action_message = "Right Turn Signal | " + received_message;
            turn_on_right_turn_signal(received_message);
            break;
        case LEFT_TURN_EVENT_ID:
            action_message = "Left Turn Signal | " + received_message;
            turn_on_left_turn_signal(received_message);
            break;
            
        case HIGH_BEAM_HEADLIGHT_EVENT_ID:
            action_message = "High Beam Headlights Signal | " + received_message;
            turn_on_high_beam_headlights(received_message);
            break;
            
        case PARKING_LEFT_EVENT_ID:
            action_message = "Parking left Signal | " + received_message;
            turn_on_parking_left_signal(received_message);
            break;
        case PARKING_RIGHT_EVENT_ID:
            action_message = "Parking right | " + received_message;
            turn_on_parking_right_signal(received_message);
            break;
        default:
            action_message = "Unknown event ID: " + std::to_string(_response->get_method());
            std::cerr << action_message << std::endl;
    }
    
    // Enregistrer dans le fichier log
    log_to_file(_response, action_message);
}

void LightsClient::on_availability(vsomeip::service_t _service, vsomeip::instance_t _instance, bool _is_available) {
    std::cout << "CLIENT: Service ID / Instance ID ["
              << std::setw(4) << std::setfill('0') << std::hex << _service << "." << _instance
              << "] is "
              << (_is_available ? "available." : "NOT available.")
              << std::endl;

    {
        std::lock_guard<std::mutex> lock(mutex_);
        service_available_ = _is_available;
    }
    condition_.notify_one();

    if (_is_available) {
        std::set<vsomeip::eventgroup_t> groups = {LIGHTS_EVENTGROUP_ID};
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, LOW_BEAM_HEADLIGHT_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, HAZARD_LIGHT_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, RIGHT_TURN_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, LEFT_TURN_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, HIGH_BEAM_HEADLIGHT_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, PARKING_LEFT_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, PARKING_RIGHT_EVENT_ID, groups);
        app_->subscribe(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, LIGHTS_EVENTGROUP_ID);
    }
}


void LightsClient::log_to_file(const std::shared_ptr<vsomeip::message> &_response, const std::string& action_message) {
    std::ofstream log_file(log_file_path, std::ios_base::app);
    
    if (log_file.is_open()) {
        log_file << message_to_string(_response) << std::endl;
        log_file << action_message << std::endl;
    } else {
        std::cerr << "Failed to open log file: " << log_file_path << std::endl;
    }
}

void LightsClient::turn_on_low_beam_headlights(const std::string &state) {
    std::string message = "Low Beam Headlights |  " + state;
    std::cout << message << std::endl;
}

void LightsClient::turn_on_hazard_lights(const std::string &state) {
    std::string message = "Hazard Lights |  " + state;
    std::cout << message << std::endl;
}

void LightsClient::turn_on_right_turn_signal(const std::string &state) {
    std::string message = "Right Turn Signal |  " + state;
    std::cout << message << std::endl;
}

void LightsClient::turn_on_left_turn_signal(const std::string &state) {
    std::string message = "Left Turn Signal | " + state;
    std::cout << message << std::endl;
}

void LightsClient::turn_on_high_beam_headlights(const std::string &state) {
    std::string message = "High Beam Headlights |  " + state;
    std::cout << message << std::endl;
}

void LightsClient::turn_on_parking_left_signal(const std::string &state) {
    std::string message = "Parking left Signal |  " + state;
    std::cout << message << std::endl;
}

void LightsClient::turn_on_parking_right_signal(const std::string &state) {
    std::string message = "Parking right Signal |  " + state;
    std::cout << message << std::endl;
}

std::string LightsClient::message_to_string(const std::shared_ptr<vsomeip::message> &_response) const {
    std::stringstream its_message;
    its_message << "CLIENT: received a notification for event ["
                << std::setw(4) << std::setfill('0') << std::hex
                << _response->get_service() << "."
                << std::setw(4) << std::setfill('0') << std::hex
                << _response->get_instance() << "."
                << std::setw(4) << std::setfill('0') << std::hex
                << _response->get_method() << "] to Client/Session ["
                << std::setw(4) << std::setfill('0') << std::hex
                << _response->get_client() << "/"
                << std::setw(4) << std::setfill('0') << std::hex
                << _response->get_session()
                << "] = ";

    std::shared_ptr<vsomeip::payload> its_payload = _response->get_payload();
    for (uint32_t i = 0; i < its_payload->get_length(); ++i) {
        its_message << std::hex << std::setw(2) << std::setfill('0')
                    << static_cast<int>(its_payload->get_data()[i]) << " ";
    }

    return its_message.str();
}