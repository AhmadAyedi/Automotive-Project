#include "climates_client.h"
#include <sstream>
#include <iomanip>

ClimateClient::ClimateClient() 
    : app_(vsomeip::runtime::get()->create_application("CLIMATE")),
      service_available_(false),
      running_(true),
      log_file_("/home/pi/vsomeip/PFE-2025/mockupClimate/src/climate_log.txt", std::ios::app) {
    
    if (!log_file_.is_open()) {
        std::cerr << "[CLIENT] Failed to open log file!" << std::endl;
    }
    
    std::signal(SIGINT, signal_handler);
}

ClimateClient::~ClimateClient() {
    stop();
    if (log_file_.is_open()) {
        log_file_.close();
    }
}

std::string ClimateClient::get_current_timestamp() {
    auto now = std::chrono::system_clock::now();
    auto in_time_t = std::chrono::system_clock::to_time_t(now);

    std::stringstream ss;
    ss << std::put_time(std::localtime(&in_time_t), "[%Y-%m-%d %H:%M:%S]");
    return ss.str();
}

void ClimateClient::log_message(const std::string& message) {
    if (log_file_.is_open()) {
        log_file_ << get_current_timestamp() << " " << message << std::endl;
    }
    std::cout << get_current_timestamp() << " " << message << std::endl;
}

void ClimateClient::log_packet(const std::shared_ptr<vsomeip::message>& _response, const std::string& payload_str) {
    std::stringstream packet_ss;
    packet_ss << "CLIENT: received a notification for event ["
              << std::setw(4) << std::setfill('0') << std::hex
              << _response->get_service() << "."
              << std::setw(4) << std::setfill('0') << std::hex
              << _response->get_instance() << "."
              << std::setw(4) << std::setfill('0') << std::hex
              << _response->get_method() << "] to Client/Session ["
              << std::setw(4) << std::setfill('0') << std::hex
              << _response->get_client() << "/"
              << std::setw(4) << std::setfill('0') << std::hex
              << _response->get_session() << "] = ";

    std::shared_ptr<vsomeip::payload> its_payload = _response->get_payload();
    for (uint32_t i = 0; i < its_payload->get_length(); ++i) {
        packet_ss << std::hex << std::setw(2) << std::setfill('0')
                 << static_cast<int>(its_payload->get_data()[i]) << " ";
    }

    log_message(packet_ss.str());
    log_message("[CLIENT] Payload: " + payload_str);
}

bool ClimateClient::init() {
    if (!app_->init()) {
        log_message("[CLIENT] Initialization failed!");
        return false;
    }

    app_->register_availability_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, 
        [this](vsomeip::service_t service, vsomeip::instance_t instance, bool is_available) {
            this->on_availability(service, instance, is_available);
        });

    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, CLASSIC_CLIMATE_EVENT_ID, 
        [this](const std::shared_ptr<vsomeip::message> &msg) {
            this->on_message(msg);
        });

    app_->register_message_handler(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID, SMART_CLIMATE_EVENT_ID, 
        [this](const std::shared_ptr<vsomeip::message> &msg) {
            this->on_message(msg);
        });

    app_->request_service(SAMPLE_SERVICE_ID, SAMPLE_INSTANCE_ID);
    return true;
}

void ClimateClient::start() {
    log_message("[CLIENT] Starting application...");
    app_->start();
}

void ClimateClient::stop() {
    running_ = false;
    if (app_) {
        app_->stop();
    }
    log_message("[CLIENT] Application stopped");
}

void ClimateClient::on_message(const std::shared_ptr<vsomeip::message> &_response) {
    std::shared_ptr<vsomeip::payload> its_payload = _response->get_payload();
    std::string payload_str(reinterpret_cast<char *>(its_payload->get_data()), its_payload->get_length());

    log_packet(_response, payload_str);

    if (_response->get_method() == CLASSIC_CLIMATE_EVENT_ID) {
        classic_climate(payload_str);
    } else if (_response->get_method() == SMART_CLIMATE_EVENT_ID) {
        smart_climate(payload_str);
    }
}

void ClimateClient::on_availability(vsomeip::service_t service, vsomeip::instance_t instance, bool is_available) {
    std::stringstream ss;
    ss << "[CLIENT] Service [" << std::hex << std::setw(4) << std::setfill('0')
       << service << "." << instance << "] is "
       << (is_available ? "AVAILABLE." : "NOT AVAILABLE.");
    log_message(ss.str());

    {
        std::lock_guard<std::mutex> lock(mutex_);
        service_available_ = is_available;
    }
    condition_.notify_one();

    if (is_available) {
        std::set<vsomeip::eventgroup_t> groups = {CLIMATE_EVENTGROUP_ID};
        app_->request_event(service, instance, CLASSIC_CLIMATE_EVENT_ID, groups);
        app_->request_event(service, instance, SMART_CLIMATE_EVENT_ID, groups);
        app_->subscribe(service, instance, CLIMATE_EVENTGROUP_ID);
    }
}

void ClimateClient::classic_climate(const std::string &state) {
    log_message("[CLIENT] Classic Climate Received: " + state);
}

void ClimateClient::smart_climate(const std::string &state) {
    log_message("[CLIENT] Smart Climate Received: " + state);
}

void ClimateClient::signal_handler(int signal) {
    std::cout << "\n[CLIENT] Received signal " << signal << ", terminating..." << std::endl;
    std::exit(signal);
}