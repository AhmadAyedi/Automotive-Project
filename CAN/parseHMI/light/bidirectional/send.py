import can
import time
import os
import threading
from datetime import datetime

# CAN IDs for each light type
LIGHT_IDS = {
    "Low Beam": 0x101,
    "High Beam": 0x102,
    "Parking Left": 0x103,
    "Parking Right": 0x104,
    "Hazard Lights": 0x105,
    "Right Turn": 0x106,
    "Left Turn": 0x107
}

# Status codes (1 byte)
STATUS_CODES = {
    "activated": 0x01,
    "desactivated": 0x00,
    "FAILED": 0xFF
}

# Reverse mappings for response parsing
LIGHT_NAMES = {
    0x101: "Low Beam",
    0x102: "High Beam",
    0x103: "Parking Left",
    0x104: "Parking Right",
    0x105: "Hazard Lights",
    0x106: "Right Turn",
    0x107: "Left Turn"
}

STATUS_NAMES = {
    0x01: "activated",
    0x00: "desactivated",
    0xFF: "FAILED"
}

class CANLightMaster:
    def __init__(self, filename):
        self.filename = filename
        self.channel = 'can0'
        self.bustype = 'socketcan'
        self.bus = None
        self.last_size = os.path.getsize(filename)
        self.running = True
        self.RESPONSE_ID = 0x200
        
        self.init_can_bus()
        self.start_response_monitor()
    
    def init_can_bus(self):
        try:
            os.system(f'sudo /sbin/ip link set {self.channel} up type can bitrate 500000')
            time.sleep(0.1)
            self.bus = can.interface.Bus(channel=self.channel, bustype=self.bustype)
            print("CAN initialized")
        except Exception as e:
            print(f"CAN init failed: {e}")
            raise
    
    def send_can_message(self, light, status):
        try:
            msg = can.Message(
                arbitration_id=LIGHT_IDS[light],
                data=[STATUS_CODES[status]],
                is_extended_id=False
            )
            self.bus.send(msg)
            print(f"Sent: {light} - {status} (ID: {hex(LIGHT_IDS[light])}, Data: {hex(STATUS_CODES[status])})")
        except Exception as e:
            print(f"Error sending CAN message: {e}")
    
    def parse_response_frame(self, data):
        """Parse response CAN data into signals"""
        if len(data) != 7:
            return None
        signals = {}
        light_order = [
            "Low Beam", "High Beam", "Parking Left", "Parking Right",
            "Hazard Lights", "Right Turn", "Left Turn"
        ]
        for i, light in enumerate(light_order):
            signals[light] = STATUS_NAMES.get(data[i], "Unknown status")
        return signals
    
    def write_response_to_file(self, signals):
        """Write response signals to light_response_signals.txt and simplified_results.txt with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Write to light_response_signals.txt (original format)
        try:
            with open("light_response_signals.txt", 'a') as f:
                f.write(f"\n--- Response at {timestamp} ---\n")
                for key, value in signals.items():
                    f.write(f"{key} = {value}\n")
                f.write("\n")
            print(f"Response signals written to light_response_signals.txt at {timestamp}")
        except Exception as e:
            print(f"Error writing to light_response_signals.txt: {e}")
        
        # Write to simplified_results.txt (ON/OFF format)
        try:
            simplified_signals = {
                key: "ON" if value == "activated" else "OFF"
                for key, value in signals.items()
            }
            with open("simplified_results.txt", 'a') as f:
                f.write(f"\n--- Response at {timestamp} ---\n")
                for key, value in simplified_signals.items():
                    f.write(f"{key} = {value}\n")
                f.write("\n")
            print(f"Simplified response signals written to simplified_results.txt at {timestamp}")
        except Exception as e:
            print(f"Error writing to simplified_results.txt: {e}")
    
    def monitor_responses(self):
        """Monitor CAN bus for response messages from slave"""
        print("Listening for response CAN messages...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg and msg.arbitration_id == self.RESPONSE_ID:
                    signals = self.parse_response_frame(msg.data)
                    if signals:
                        print("\nReceived Response Signals:")
                        for key, value in signals.items():
                            print(f"{key}: {value}")
                        self.write_response_to_file(signals)
                    else:
                        print(f"Invalid response data: {msg.data.hex()}")
        except Exception as e:
            print(f"Response monitoring error: {e}")
    
    def start_response_monitor(self):
        """Start a thread to monitor response messages"""
        self.response_thread = threading.Thread(target=self.monitor_responses, daemon=True)
        self.response_thread.start()
    
    def monitor_file(self):
        print(f"Monitoring {self.filename} for new light status updates...")
        print("Add new lines to the file to send CAN messages")
        
        try:
            while self.running:
                current_size = os.path.getsize(self.filename)
                
                if current_size > self.last_size:
                    with open(self.filename, 'r') as f:
                        f.seek(self.last_size)
                        new_content = f.read()
                        self.last_size = current_size
                        
                        lines = new_content.split('\n')
                        for line in lines:
                            if line.strip() and line.startswith("Light:") and "Result:" in line:
                                try:
                                    parts = line.split('|')
                                    light = parts[0].split(':')[1].strip()
                                    status = parts[1].split(':')[1].strip()
                                    
                                    if light in LIGHT_IDS and status in STATUS_CODES:
                                        self.send_can_message(light, status)
                                    else:
                                        print(f"Ignoring unknown light/status: {line}")
                                except IndexError:
                                    print(f"Malformed line: {line}")
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        self.running = False
        if self.response_thread.is_alive():
            self.response_thread.join(timeout=0.5)
        if self.bus:
            self.bus.shutdown()
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        print("Shutdown complete")

if __name__ == "__main__":
    master = CANLightMaster("analysis_results.txt")
    master.monitor_file()