import can
import time
import os
import threading
from datetime import datetime

# CAN IDs for each window type
WINDOW_IDS = {
    "DR": 0x201,
    "PS": 0x202,
    "DRS": 0x203,
    "PRS": 0x204
}

# Response ID for slave responses
RESPONSE_ID = 0x300

class CANWindowMaster:
    def __init__(self, filename):
        self.filename = filename
        self.channel = 'can0'
        self.bustype = 'socketcan'
        self.bus = None
        self.last_size = os.path.getsize(filename)
        self.running = True
        
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
    
    def send_can_message(self, window, level):
        try:
            msg = can.Message(
                arbitration_id=WINDOW_IDS[window],
                data=[level],
                is_extended_id=False
            )
            self.bus.send(msg)
            print(f"Sent: {window} - Level: {level}% (ID: {hex(WINDOW_IDS[window])}, Data: {level})")
        except Exception as e:
            print(f"Error sending CAN message: {e}")
    
    def parse_response_frame(self, data):
        """Parse response CAN data into window levels"""
        if len(data) != 4:
            return None
        levels = {
            "DR": data[0],
            "PS": data[1],
            "DRS": data[2],
            "PRS": data[3]
        }
        return levels
    
    def write_response_to_file(self, levels):
        """Write response levels to window_response.txt"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            with open("window_response.txt", 'a') as f:
                f.write(f"\n--- Response at {timestamp} ---\n")
                for window, level in levels.items():
                    f.write(f"{window} = {level}%\n")
                f.write("\n")
            print(f"Response levels written to window_response.txt at {timestamp}")
        except Exception as e:
            print(f"Error writing to window_response.txt: {e}")
    
    def monitor_responses(self):
        """Monitor CAN bus for response messages from slave"""
        print("Listening for response CAN messages...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg and msg.arbitration_id == RESPONSE_ID:
                    levels = self.parse_response_frame(msg.data)
                    if levels:
                        print("\nReceived Window Levels:")
                        for window, level in levels.items():
                            print(f"{window}: {level}%")
                        self.write_response_to_file(levels)
                    else:
                        print(f"Invalid response data: {msg.data.hex()}")
        except Exception as e:
            print(f"Response monitoring error: {e}")
    
    def start_response_monitor(self):
        """Start a thread to monitor response messages"""
        self.response_thread = threading.Thread(target=self.monitor_responses, daemon=True)
        self.response_thread.start()
    
    def monitor_file(self):
        print(f"Monitoring {self.filename} for new window status updates...")
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
                            if line.strip() and line.startswith("Window:"):
                                try:
                                    parts = line.split('|')
                                    window = parts[0].split(':')[1].strip()
                                    level_part = parts[2].split(':')[1].strip()
                                    level = int(level_part.replace('%', ''))
                                    
                                    if window in WINDOW_IDS and 0 <= level <= 100:
                                        self.send_can_message(window, level)
                                    else:
                                        print(f"Ignoring unknown window/level: {line}")
                                except (IndexError, ValueError) as e:
                                    print(f"Malformed line: {line} - Error: {e}")
                
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
    master = CANWindowMaster("windows_analysis.txt")
    master.monitor_file()