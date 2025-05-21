#include "vehicle_client.h"
#include <iostream>
#include <ctime>
#include <iomanip>
#include <chrono>
#include <thread>

VehicleClient::VehicleClient() 
    : app_(vsomeip::runtime::get()->create_application()),
      lights_service_available_(false),
      doors_service_available_(false) {
}

VehicleClient::~VehicleClient() {
    stop();
}

bool VehicleClient::init() {
    if (!app_->init()) {
        std::cerr << "Failed to initialize vsomeip application!" << std::endl;
        return false;
    }

    // Enregistrement des handlers
    app_->register_availability_handler(LIGHTS_SERVICE_ID, LIGHTS_INSTANCE_ID, 
        [this](vsomeip::service_t s, vsomeip::instance_t i, bool a) { 
            this->on_availability(s, i, a); 
        });
        
    app_->register_availability_handler(DOORS_SERVICE_ID, DOORS_INSTANCE_ID, 
        [this](vsomeip::service_t s, vsomeip::instance_t i, bool a) { 
            this->on_availability(s, i, a); 
        });

    app_->register_message_handler(
        vsomeip::ANY_SERVICE, vsomeip::ANY_INSTANCE, vsomeip::ANY_METHOD,
        [this](const std::shared_ptr<vsomeip::message> &m) {
            this->on_message(m);
        });

    // Demande des services
    app_->request_service(LIGHTS_SERVICE_ID, LIGHTS_INSTANCE_ID);
    app_->request_service(DOORS_SERVICE_ID, DOORS_INSTANCE_ID);
    
    return true;
}

void VehicleClient::start() {
    app_->start();
}

void VehicleClient::stop() {
    app_->stop();
}

void VehicleClient::on_message(const std::shared_ptr<vsomeip::message> &_response) {
    std::cout << message_to_string(_response) << std::endl;

    // Routage des messages vers le bon handler
    if (_response->get_service() == LIGHTS_SERVICE_ID) {
        handle_lights_events(_response);
    } 
    else if (_response->get_service() == DOORS_SERVICE_ID) {
        handle_doors_events(_response);
    }
}

void VehicleClient::on_availability(vsomeip::service_t _service, vsomeip::instance_t _instance, bool _is_available) {
    std::cout << "Service ["
              << std::setw(4) << std::setfill('0') << std::hex << _service << "." << _instance
              << "] is "
              << (_is_available ? "available." : "NOT available.")
              << std::endl;

    if (_service == LIGHTS_SERVICE_ID && _instance == LIGHTS_INSTANCE_ID) {
        std::lock_guard<std::mutex> lock(mutex_);
        lights_service_available_ = _is_available;
        
        if (_is_available) {
            init_lights_service();
        }
    } 
    else if (_service == DOORS_SERVICE_ID && _instance == DOORS_INSTANCE_ID) {
        std::lock_guard<std::mutex> lock(mutex_);
        doors_service_available_ = _is_available;
        
        if (_is_available) {
            init_doors_service();
        }
    }
    
    condition_.notify_one();
}

void VehicleClient::init_lights_service() {
    std::set<vsomeip::eventgroup_t> groups = {LIGHTS_EVENTGROUP_ID};
    
    app_->request_event(LIGHTS_SERVICE_ID, LIGHTS_INSTANCE_ID, LOW_BEAM_HEADLIGHT_EVENT_ID, groups);
    app_->request_event(LIGHTS_SERVICE_ID, LIGHTS_INSTANCE_ID, HAZARD_LIGHT_EVENT_ID, groups);
    app_->request_event(LIGHTS_SERVICE_ID, LIGHTS_INSTANCE_ID, RIGHT_TURN_EVENT_ID, groups);
    app_->request_event(LIGHTS_SERVICE_ID, LIGHTS_INSTANCE_ID, LEFT_TURN_EVENT_ID, groups);
    app_->request_event(LIGHTS_SERVICE_ID, LIGHTS_INSTANCE_ID, HIGH_BEAM_HEADLIGHT_EVENT_ID, groups);
    app_->request_event(LIGHTS_SERVICE_ID, LIGHTS_INSTANCE_ID, PARKING_LEFT_EVENT_ID, groups);
    app_->request_event(LIGHTS_SERVICE_ID, LIGHTS_INSTANCE_ID, PARKING_RIGHT_EVENT_ID, groups);
    
    app_->subscribe(LIGHTS_SERVICE_ID, LIGHTS_INSTANCE_ID, LIGHTS_EVENTGROUP_ID);
}

void VehicleClient::init_doors_service() {
    std::set<vsomeip::eventgroup_t> groups = {DOORS_EVENTGROUP_ID};
    
    app_->request_event(DOORS_SERVICE_ID, DOORS_INSTANCE_ID, KEY_EVENT_ID, groups);
    app_->request_event(DOORS_SERVICE_ID, DOORS_INSTANCE_ID, FRONT_RIGHT_DOOR_EVENT_ID, groups);
    app_->request_event(DOORS_SERVICE_ID, DOORS_INSTANCE_ID, REAR_RIGHT_DOOR_EVENT_ID, groups);
    app_->request_event(DOORS_SERVICE_ID, DOORS_INSTANCE_ID, FRONT_LEFT_DOOR_EVENT_ID, groups);
    app_->request_event(DOORS_SERVICE_ID, DOORS_INSTANCE_ID, REAR_LEFT_DOOR_EVENT_ID, groups);
    
    app_->subscribe(DOORS_SERVICE_ID, DOORS_INSTANCE_ID, DOORS_EVENTGROUP_ID);
}

void VehicleClient::handle_lights_events(const std::shared_ptr<vsomeip::message> &_response) {
    std::shared_ptr<vsomeip::payload> its_payload = _response->get_payload();
    std::string received_message(reinterpret_cast<char *>(its_payload->get_data()), 
                               its_payload->get_length());

    std::string action_message;
    
    switch (_response->get_method()) {
        case LOW_BEAM_HEADLIGHT_EVENT_ID:
            action_message = "Low Beam Headlights | " + received_message;
            break;
        case HAZARD_LIGHT_EVENT_ID:
            action_message = "Hazard Lights | " + received_message;
            break;
        case RIGHT_TURN_EVENT_ID:
            action_message = "Right Turn Signal | " + received_message;
            break;
        case LEFT_TURN_EVENT_ID:
            action_message = "Left Turn Signal | " + received_message;
            break;
        case HIGH_BEAM_HEADLIGHT_EVENT_ID:
            action_message = "High Beam Headlights | " + received_message;
            break;
        case PARKING_LEFT_EVENT_ID:
            action_message = "Parking Left Signal | " + received_message;
            break;
        case PARKING_RIGHT_EVENT_ID:
            action_message = "Parking Right Signal | " + received_message;
            break;
        default:
            action_message = "Unknown lights event: " + std::to_string(_response->get_method());
            std::cerr << action_message << std::endl;
    }
    
    log_to_file(lights_log_path, _response, action_message);
    std::cout << action_message << std::endl;
}

void VehicleClient::handle_doors_events(const std::shared_ptr<vsomeip::message> &_response) {
    std::shared_ptr<vsomeip::payload> its_payload = _response->get_payload();
    std::string received_message(reinterpret_cast<char *>(its_payload->get_data()), 
                               its_payload->get_length());

    std::string action_message;
    
    switch (_response->get_method()) {
        case FRONT_RIGHT_DOOR_EVENT_ID:
            action_message = "Front Right Door | Status: " + received_message;
            break;
        case REAR_RIGHT_DOOR_EVENT_ID:
            action_message = "Rear Right Door | Status: " + received_message;
            break;
        case FRONT_LEFT_DOOR_EVENT_ID:
            action_message = "Front Left Door | Status: " + received_message;
            break;
        case REAR_LEFT_DOOR_EVENT_ID:
            action_message = "Rear Left Door | Status: " + received_message;
            break;
        case KEY_EVENT_ID:
            action_message = "Key | Status: " + received_message;
            break;
        default:
            action_message = "Unknown doors event: " + std::to_string(_response->get_method());
            std::cerr << action_message << std::endl;
    }
    
    log_to_file(doors_log_path, _response, action_message);
    std::cout << action_message << std::endl;
}

void VehicleClient::log_to_file(const std::string &file_path, const std::shared_ptr<vsomeip::message> &_response, const std::string& action_message) {
    std::ofstream log_file(file_path, std::ios_base::app);
    
    if (log_file.is_open()) {
        // Ajout d'un timestamp
        auto now = std::chrono::system_clock::now();
        auto now_time = std::chrono::system_clock::to_time_t(now);
        log_file << std::put_time(std::localtime(&now_time), "%Y-%m-%d %H:%M:%S") << " | ";
        
        log_file << message_to_string(_response) << std::endl;
        log_file << "    " << action_message << std::endl;
    } else {
        std::cerr << "Failed to open log file: " << file_path << std::endl;
    }
}

std::string VehicleClient::message_to_string(const std::shared_ptr<vsomeip::message> &_response) const {
    std::stringstream its_message;
    its_message << "Received notification ["
                << std::setw(4) << std::setfill('0') << std::hex
                << _response->get_service() << "."
                << std::setw(4) << std::setfill('0') << std::hex
                << _response->get_instance() << "."
                << std::setw(4) << std::setfill('0') << std::hex
                << _response->get_method() << "] Client/Session ["
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