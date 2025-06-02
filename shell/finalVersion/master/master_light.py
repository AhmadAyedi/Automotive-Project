import can
import time
import os
import threading
from datetime import datetime
import mysql.connector
from mysql.connector import Error

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

# Response IDs (same as light IDs for two-way communication)
RESPONSE_IDS = {
    "Low Beam": 0x101,
    "High Beam": 0x102,
    "Parking Left": 0x103,
    "Parking Right": 0x104,
    "Hazard Lights": 0x105,
    "Right Turn": 0x106,
    "Left Turn": 0x107
}

# Status codes for CAN communication
STATUS_CODES = {
    "ACTIVATED": 0x01,
    "DEACTIVATED": 0x00,
    "FAILED": 0xFF,
    "INVALID": 0xFE
}

# Mode codes
MODE_CODES = {
    "FAHREN": 0x01,
    "STAND": 0x02,
    "PARKING": 0x03,
    "WOHNEN": 0x04
}

# Reverse mappings
STATUS_NAMES = {
    0x01: "ON",
    0x00: "OFF",
    0xFF: "FAILED",
    0xFE: "INVALID"
}

MODE_NAMES = {
    0x01: "Fahren",
    0x02: "Stand",
    0x03: "Parking",
    0x04: "Wohnen"
}

# Database event IDs
EVENT_IDS = {
    0x101: 5,  # Low Beam
    0x102: 6,  # High Beam
    0x103: 3,  # Parking Left
    0x104: 4,  # Parking Right
    0x105: 7,  # Hazard Lights
    0x106: 9,  # Right Turn
    0x107: 8   # Left Turn
}

class CANLightMaster:
    def __init__(self, filename):
        self.filename = filename
        self.channel = 'can0'
        self.bustype = 'socketcan'
        self.bus = None
        self.last_size = os.path.getsize(filename)
        self.running = True
        self.db_connection = None
        self.db_cursor = None
        self.last_modified_light = None
        self.last_processed_status = {light: None for light in LIGHT_IDS}
        self.last_processed_mode = {light: None for light in LIGHT_IDS}
        
        self.init_can_bus()
        self.init_db_connection()
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
    
    def init_db_connection(self):
        try:
            self.db_connection = mysql.connector.connect(
                host="10.20.0.23",
                user="myuser1",
                password="root",
                database="khalil"
            )
            self.db_cursor = self.db_connection.cursor()
            print("MySQL database connection established")
            
            create_table_query = """
            CREATE TABLE IF NOT EXISTS protocol_data (
                event_id INT PRIMARY KEY,
                message INT NOT NULL,
                timestamp DATETIME
            )
            """
            self.db_cursor.execute(create_table_query)
            
            self.db_cursor.execute("SELECT event_id FROM protocol_data")
            existing_ids = {row[0] for row in self.db_cursor.fetchall()}
            
            required_ids = {3, 4, 5, 6, 7, 8, 9}
            missing_ids = required_ids - existing_ids
            if missing_ids:
                insert_query = """
                INSERT INTO protocol_data (event_id, message, timestamp)
                VALUES (%s, %s, %s)
                """
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for event_id in missing_ids:
                    self.db_cursor.execute(insert_query, (event_id, 0, timestamp))
                self.db_connection.commit()
                print(f"Initialized {len(missing_ids)} missing rows in protocol_data")
            
            self.db_cursor.execute("DELETE FROM protocol_data WHERE event_id NOT IN (3, 4, 5, 6, 7, 8, 9)")
            self.db_connection.commit()
            
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            raise
    
    def send_can_message(self, light, status, mode):
        try:
            msg = can.Message(
                arbitration_id=LIGHT_IDS[light],
                data=[STATUS_CODES[status], MODE_CODES[mode]],
                is_extended_id=False
            )
            self.bus.send(msg)
            print(f"Sent: {light} - {status} - {mode} (ID: {hex(LIGHT_IDS[light])}, Data: {[hex(STATUS_CODES[status]), hex(MODE_CODES[mode])]})")
            self.last_modified_light = (light, LIGHT_IDS[light])
        except Exception as e:
            print(f"Error sending CAN message: {e}")
    
    def parse_response_frame(self, msg):
        """Parse response CAN message from slave"""
        try:
            light = next((name for name, can_id in RESPONSE_IDS.items() if can_id == msg.arbitration_id), None)
            if light and len(msg.data) >= 2:
                status_code = msg.data[0]
                mode_code = msg.data[1]
                
                return {
                    light: {
                        "status": STATUS_NAMES.get(status_code, f"Unknown: {hex(status_code)}"),
                        "mode": MODE_NAMES.get(mode_code, f"Unknown: {hex(mode_code)}")
                    }
                }
        except (IndexError, ValueError) as e:
            print(f"Error parsing response: {e}")
        return None
    
    def write_response_to_file(self, status):
        """Write response status to lighting_response.txt"""
        try:
            with open("lighting_response.txt", 'a') as f:
                for light, data in status.items():
                    f.write(f"{light} | {data['status']} | {data['mode']}\n")
            print("Response status written to lighting_response.txt")
        except Exception as e:
            print(f"Error writing to lighting_response.txt: {e}")
    
    def update_database(self, status):
        """Update the database with light status (simplified to match previous version)"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            if not self.db_connection.is_connected():
                self.init_db_connection()
            
            if self.last_modified_light:
                light_name, light_id = self.last_modified_light
                light_data = status.get(light_name)
                if light_data:
                    new_message = 1 if light_data['status'] == "ON" else 0
                    event_id = EVENT_IDS[light_id]
                    
                    select_query = "SELECT message FROM protocol_data WHERE event_id = %s"
                    self.db_cursor.execute(select_query, (event_id,))
                    result = self.db_cursor.fetchone()
                    
                    if result:
                        current_message = result[0]
                        if current_message != new_message:
                            update_query = """
                            UPDATE protocol_data
                            SET message = %s, timestamp = %s
                            WHERE event_id = %s
                            """
                            self.db_cursor.execute(update_query, (new_message, timestamp, event_id))
                            self.db_connection.commit()
                            print(f"Updated MySQL database: event_id={event_id}, message={new_message} at {timestamp}")
                        else:
                            print(f"No update needed for {light_name}: message unchanged (current={current_message}, new={new_message})")
                    else:
                        print(f"Error: No row found for event_id={event_id}")
                else:
                    print(f"No status data found for {light_name} in response")
            else:
                print("No modified light to process for database update")
                
        except Error as e:
            print(f"Error updating MySQL database: {e}")
            if not self.db_connection.is_connected():
                print("Database connection lost; will attempt to reconnect on next update")
    
    def monitor_responses(self):
        """Monitor CAN bus for response messages from slave"""
        print("Listening for response CAN messages...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg and msg.arbitration_id in RESPONSE_IDS.values():
                    status = self.parse_response_frame(msg)
                    if status:
                        print("\nReceived Light Status:")
                        for light, data in status.items():
                            print(f"{light}: {data['status']} | {data['mode']}")
                        self.write_response_to_file(status)
                        self.update_database(status)
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
                        
                        for line in new_content.split('\n'):
                            if line.strip() and line.startswith("Light:"):
                                try:
                                    parts = [p.strip() for p in line.split('|')]
                                    if len(parts) < 3:
                                        print(f"Skipping incomplete line: {line}")
                                        continue
                                        
                                    light = parts[0].split(':')[1].strip()
                                    status = parts[1].split(':')[1].strip().upper()
                                    mode = parts[2].split(':')[1].strip().upper()
                                    
                                    if (light in LIGHT_IDS and 
                                        status in STATUS_CODES and 
                                        mode in MODE_CODES):
                                        
                                        if (self.last_processed_status[light] != status or 
                                            self.last_processed_mode[light] != mode):
                                            
                                            self.send_can_message(light, status, mode)
                                            self.last_processed_status[light] = status
                                            self.last_processed_mode[light] = mode
                                            print(f"Processed status/mode change for {light}: {status}/{mode}")
                                        else:
                                            print(f"No change in {light} status/mode, skipping")
                                    else:
                                        print(f"Ignoring unknown light/status/mode: {line}")
                                except (IndexError, ValueError) as e:
                                    print(f"Malformed line: {line} - Error: {e}")
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        self.running = False
        if hasattr(self, 'response_thread') and self.response_thread.is_alive():
            self.response_thread.join(timeout=0.5)
        if self.bus:
            self.bus.shutdown()
        if self.db_connection and self.db_connection.is_connected():
            self.db_cursor.close()
            self.db_connection.close()
            print("MySQL connection closed")
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        print("Shutdown complete")

if __name__ == "__main__":
    master = CANLightMaster("light_analysis.txt")
    master.monitor_file()