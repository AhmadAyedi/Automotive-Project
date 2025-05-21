#include "doors_client.h"
#include <iostream>

DoorsClient::DoorsClient() 
    : app_(vsomeip::runtime::get()->create_application("DOORS")),
      service_available_(false) {
}

DoorsClient::~DoorsClient() {
    stop();
}

bool DoorsClient::init() {
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
                                 KEY_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 FRONT_RIGHT_DOOR_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 REAR_RIGHT_DOOR_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 FRONT_LEFT_DOOR_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 REAR_LEFT_DOOR_EVENT_ID, message_handler);
    
    app_->request_service(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID);
    
    return true;
}

void DoorsClient::start() {
    app_->start();
}

void DoorsClient::stop() {
    app_->stop();
}

void DoorsClient::on_message(const std::shared_ptr<vsomeip::message> &_response) {
    std::cout << message_to_string(_response) << std::endl;

    std::shared_ptr<vsomeip::payload> its_payload = _response->get_payload();
    std::string received_message(reinterpret_cast<char *>(its_payload->get_data()), 
                               its_payload->get_length());

    std::string action_message;
    
    switch (_response->get_method()) {
        case FRONT_RIGHT_DOOR_EVENT_ID:
            action_message = "Front Right Door | " + received_message;
            front_right_door(received_message);
            break;
        case REAR_RIGHT_DOOR_EVENT_ID:
            action_message = "Rear Right Door | " + received_message;
            rear_right_door(received_message);
            break;
        case FRONT_LEFT_DOOR_EVENT_ID:
            action_message = "Front Left Door | " + received_message;
            front_left_door(received_message);
            break;
        case REAR_LEFT_DOOR_EVENT_ID:
            action_message = "Rear Left Door | " + received_message;
            rear_left_door(received_message);
            break;
        case KEY_EVENT_ID:
            action_message = "Key | " + received_message;
            key_door(received_message);
            break;
        default:
            action_message = "Unknown event ID: " + std::to_string(_response->get_method());
            std::cerr << action_message << std::endl;
    }
    
    log_to_file(_response, action_message);
}

void DoorsClient::on_availability(vsomeip::service_t _service, vsomeip::instance_t _instance, bool _is_available) {
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
        std::set<vsomeip::eventgroup_t> groups = {DOORS_EVENTGROUP_ID};
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, KEY_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, FRONT_RIGHT_DOOR_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, REAR_RIGHT_DOOR_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, FRONT_LEFT_DOOR_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, REAR_LEFT_DOOR_EVENT_ID, groups);
        app_->subscribe(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, DOORS_EVENTGROUP_ID);
    }
}


void DoorsClient::log_to_file(const std::shared_ptr<vsomeip::message> &_response, const std::string& action_message) {
    std::ofstream log_file(log_file_path, std::ios_base::app);
    
    if (log_file.is_open()) {
        log_file << message_to_string(_response) << std::endl;
        log_file << action_message << std::endl;
    } else {
        std::cerr << "Failed to open log file: " << log_file_path << std::endl;
    }
}

void DoorsClient::front_right_door(const std::string &state) {
    std::string message = "Front Right Door | " + state;
    std::cout << message << std::endl;
}

void DoorsClient::rear_right_door(const std::string &state) {
    std::string message = "Rear Right Door | " + state;
    std::cout << message << std::endl;
}

void DoorsClient::front_left_door(const std::string &state) {
    std::string message = "Front Left Door | " + state;
    std::cout << message << std::endl;
}

void DoorsClient::rear_left_door(const std::string &state) {
    std::string message = "Rear Left Door | " + state;
    std::cout << message << std::endl;
}

void DoorsClient::key_door(const std::string &state) {
    std::string message = "Key | " + state;
    std::cout << message << std::endl;
}

std::string DoorsClient::message_to_string(const std::shared_ptr<vsomeip::message> &_response) const {
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