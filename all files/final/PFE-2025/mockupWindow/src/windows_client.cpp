#include "windows_client.h"
#include <iostream>
#include <ctime>
#include <iomanip>
#include <chrono>

WindowsClient::WindowsClient() 
    : app_(vsomeip::runtime::get()->create_application("CLIENT")),
      service_available_(false) {
}

WindowsClient::~WindowsClient() {
    stop();
}

bool WindowsClient::init() {
    if (!app_->init()) {
        std::cerr << "CLIENT: Failed to initialize vsomeip application!" << std::endl;
        return false;
    }

    // Enregistrement des handlers avec lambdas
    app_->register_availability_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
        [this](vsomeip::service_t s, vsomeip::instance_t i, bool a) {
            this->on_availability(s, i, a);
        });
    
    auto message_handler = [this](const std::shared_ptr<vsomeip::message> &m) {
        this->on_message(m);
    };

    // Enregistrement des handlers de message
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 DRIVER_WINDOW_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 REAR_DRIVER_WINDOW_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 PASSENGER_WINDOW_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 REAR_PASSENGER_EVENT_ID, message_handler);
    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
                                 SAFETY_EVENT_ID, message_handler);
    
    app_->request_service(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID);
    
    return true;
}

void WindowsClient::start() {
    app_->start();
}

void WindowsClient::stop() {
    app_->stop();
}

std::string WindowsClient::get_current_timestamp() {
    auto now = std::chrono::system_clock::now();
    auto in_time_t = std::chrono::system_clock::to_time_t(now);

    std::stringstream ss;
    ss << std::put_time(std::localtime(&in_time_t), "[%H:%M:%S]");
    return ss.str();
}

void WindowsClient::log_to_file(const std::shared_ptr<vsomeip::message> &_response, const std::string& action_message) {
    std::ofstream log_file(log_file_path, std::ios_base::app);
    
    if (log_file.is_open()) {
        log_file << get_current_timestamp() << " " << message_to_string(_response) << std::endl;
        log_file << get_current_timestamp() << " " << action_message << std::endl;
    } else {
        std::cerr << get_current_timestamp() << " Failed to open log file: " << log_file_path << std::endl;
    }
}

void WindowsClient::on_message(const std::shared_ptr<vsomeip::message> &response) {
    std::cout << get_current_timestamp() << " " << message_to_string(response) << std::endl;

    std::shared_ptr<vsomeip::payload> payload = response->get_payload();
    std::string received_message(reinterpret_cast<char *>(payload->get_data()), 
                               payload->get_length());

    std::string action_message;
    
    switch (response->get_method()) {
        case DRIVER_WINDOW_EVENT_ID:
            action_message = "Driver Window | " + received_message;
            driver_window(received_message);
            break;
        case REAR_DRIVER_WINDOW_EVENT_ID:
            action_message = "Rear Driver Window | " + received_message;
            rear_driver_window(received_message);
            break;
        case PASSENGER_WINDOW_EVENT_ID:
            action_message = "Passenger Window | " + received_message;
            passenger_window(received_message);
            break;
        case REAR_PASSENGER_EVENT_ID:
            action_message = "Rear Passenger Window | " + received_message;
            rear_passenger_window(received_message);
            break;
        case SAFETY_EVENT_ID:
            action_message = "Safety System | " + received_message;
            safety_window(received_message);
            break;
        default:
            action_message = "Unknown event ID: " + std::to_string(response->get_method());
            std::cerr << get_current_timestamp() << " " << action_message << std::endl;
    }
    
    log_to_file(response, action_message);
}

void WindowsClient::on_availability(vsomeip::service_t service, 
                                  vsomeip::instance_t instance, 
                                  bool is_available) {
    std::cout << get_current_timestamp() << " CLIENT: Service ID / Instance ID ["
              << std::setw(4) << std::setfill('0') << std::hex << service << "." << instance
              << "] is "
              << (is_available ? "available." : "NOT available.")
              << std::endl;

    {
        std::lock_guard<std::mutex> lock(mutex_);
        service_available_ = is_available;
    }
    condition_.notify_one();

    if (is_available) {
        std::set<vsomeip::eventgroup_t> groups = {WINDOW_EVENTGROUP_ID};
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, DRIVER_WINDOW_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, REAR_DRIVER_WINDOW_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, PASSENGER_WINDOW_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, REAR_PASSENGER_EVENT_ID, groups);
        app_->request_event(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, SAFETY_EVENT_ID, groups);
        app_->subscribe(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, WINDOW_EVENTGROUP_ID);
    }
}

void WindowsClient::driver_window(const std::string &state) {
    std::string message = get_current_timestamp() + " Driver Window | " + state;
    std::cout << message << std::endl;
}

void WindowsClient::rear_driver_window(const std::string &state) {
    std::string message = get_current_timestamp() + " Rear Driver Window | " + state;
    std::cout << message << std::endl;
}

void WindowsClient::passenger_window(const std::string &state) {
    std::string message = get_current_timestamp() + " Passenger Window | " + state;
    std::cout << message << std::endl;
}

void WindowsClient::rear_passenger_window(const std::string &state) {
    std::string message = get_current_timestamp() + " Rear Passenger Window | " + state;
    std::cout << message << std::endl;
}

void WindowsClient::safety_window(const std::string &state) {
    std::string message = get_current_timestamp() + " Safety System | " + state;
    std::cout << message << std::endl;
}

std::string WindowsClient::message_to_string(const std::shared_ptr<vsomeip::message> &response) const {
    std::stringstream message_stream;
    message_stream << "CLIENT: received a notification for event ["
                   << std::setw(4) << std::setfill('0') << std::hex
                   << response->get_service() << "."
                   << std::setw(4) << std::setfill('0') << std::hex
                   << response->get_instance() << "."
                   << std::setw(4) << std::setfill('0') << std::hex
                   << response->get_method() << "] to Client/Session ["
                   << std::setw(4) << std::setfill('0') << std::hex
                   << response->get_client() << "/"
                   << std::setw(4) << std::setfill('0') << std::hex
                   << response->get_session()
                   << "] = ";

    std::shared_ptr<vsomeip::payload> payload = response->get_payload();
    for (uint32_t i = 0; i < payload->get_length(); ++i) {
        message_stream << std::hex << std::setw(2) << std::setfill('0')
                       << static_cast<int>(payload->get_data()[i]) << " ";
    }

    return message_stream.str();
}