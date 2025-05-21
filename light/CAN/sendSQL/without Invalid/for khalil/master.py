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

# Status codes for CAN communication (1 byte)
STATUS_CODES = {
    "activated": 0x01,
    "desactivated": 0x00,
    "FAILED": 0xFF
}

# Database event IDs
EVENT_IDS = {
    0x101: 11,  # Low Beam
    0x102: 12,  # High Beam
    0x103: 98,  # Parking Left
    0x104: 99,  # Parking Right
    0x105: 13,  # Hazard Lights
    0x106: 15,  # Right Turn
    0x107: 14   # Left Turn
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
        self.bus = None
        self.last_size = os.path.getsize(filename)
        self.running = True
        self.RESPONSE_ID = 0x200
        self.db_connection = None
        self.db_cursor = None
        self.last_modified_light = None  # Track the last modified light (light_name, light_id)
        self.last_processed_status = {light: None for light in LIGHT_IDS}  # Track last processed status
        
        self.init_can_bus()
        self.init_db_connection()
        self.start_response_monitor()
    
    def init_can_bus(self):
        try:
            os.system(f'sudo /sbin/ip link set {self.channel} down 2>/dev/null')
            time.sleep(0.1)
            os.system(f'sudo /sbin/ip link set {self.channel} up type can bitrate 500000')
            time.sleep(0.1)
            self.bus = can.interface.Bus(interface='socketcan', channel=self.channel)
            print("CAN initialized")
        except Exception as e:
            print(f"CAN init failed: {e}")
            raise
    
    def init_db_connection(self):
        try:
            self.db_connection = mysql.connector.connect(
                host="10.20.0.23",
                user="monuserr",
                password="khalil",
                database="khalil"
            )
            self.db_cursor = self.db_connection.cursor()
            print("MySQL database connection established")
            
            # Ensure the protocol_data table exists and has exactly 7 rows
            create_table_query = """
            CREATE TABLE IF NOT EXISTS protocol_data (
                event_id INT PRIMARY KEY,
                message INT NOT NULL,
                timestamp DATETIME
            )
            """
            self.db_cursor.execute(create_table_query)
            
            # Check existing event_ids
            self.db_cursor.execute("SELECT event_id FROM protocol_data")
            existing_ids = {row[0] for row in self.db_cursor.fetchall()}
            
            # Initialize rows for event_ids 3, 4, 5, 6, 7, 8, 9 if not present
            required_ids = {11, 12, 98, 99, 13, 15, 14}
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
            
            # Remove any extra rows
            self.db_cursor.execute("DELETE FROM protocol_data WHERE event_id NOT IN (11, 12, 98, 99, 13, 15, 14)")
            self.db_connection.commit()
            
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
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
        if len(data) != 7:
            print(f"Invalid response frame length: {len(data)} bytes")
            return None
        
        signals = {}
        light_order = [
            0x101,  # Low Beam
            0x102,  # High Beam
            0x103,  # Parking Left
            0x104,  # Parking Right
            0x105,  # Hazard Lights
            0x106,  # Right Turn
            0x107   # Left Turn
        ]
        
        for i, light_id in enumerate(light_order):
            signals[light_id] = data[i]
        return signals
    
    def write_response_to_file(self, signals):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Write all signals to files for logging
        try:
            with open("light_response_signals.txt", 'a') as f:
                f.write(f"\n--- Response at {timestamp} ---\n")
                for light_id, status_code in signals.items():
                    light_name = LIGHT_NAMES.get(light_id, f"Unknown ID: {hex(light_id)}")
                    status_name = STATUS_NAMES.get(status_code, f"Unknown status: {hex(status_code)}")
                    f.write(f"{light_name} (ID: {hex(light_id)}) = {status_name} (Code: {hex(status_code)})\n")
                f.write("\n")
            print(f"Response signals written to light_response_signals.txt at {timestamp}")
        except Exception as e:
            print(f"Error writing to light_response_signals.txt: {e}")
        
        try:
            with open("simplified_results.txt", 'a') as f:
                for light_id, status_code in signals.items():
                    f.write(f"{hex(light_id)} = {hex(status_code)}\n")
            print("Simplified response signals written to simplified_results.txt")
        except Exception as e:
            print(f"Error writing to simplified_results.txt: {e}")
        
        # Update the message column for the modified light in the database only if the status has changed
        try:
            if not self.db_connection.is_connected():
                self.init_db_connection()
            
            if self.last_modified_light:
                light_name, light_id = self.last_modified_light
                status_code = signals.get(light_id, 0)  # Get status from response frame
                new_message = 1 if status_code == 1 else 0
                
                # Retrieve current message value from database
                select_query = "SELECT message FROM protocol_data WHERE event_id = %s"
                self.db_cursor.execute(select_query, (EVENT_IDS[light_id],))
                result = self.db_cursor.fetchone()
                
                if result:
                    current_message = result[0]
                    if current_message != new_message:
                        # Update only if the message value has changed
                        update_query = """
                        UPDATE protocol_data
                        SET message = %s, timestamp = %s
                        WHERE event_id = %s
                        """
                        data_to_update = (new_message, timestamp, EVENT_IDS[light_id])
                        self.db_cursor.execute(update_query, data_to_update)
                        self.db_connection.commit()
                        print(f"Updated MySQL database: event_id={EVENT_IDS[light_id]}, message={new_message} at {timestamp}")
                    else:
                        print(f"No update needed for {light_name}: message unchanged (current={current_message}, new={new_message})")
                else:
                    print(f"Error: No row found for event_id={EVENT_IDS[light_id]}")
            else:
                print("No modified light to process for database update")
        except Error as e:
            print(f"Error updating MySQL database: {e}")
            print(f"Failed data: {data_to_update if 'data_to_update' in locals() else 'N/A'}")
            if not self.db_connection.is_connected():
                print("Database connection lost; will attempt to reconnect on next update")
    
    def monitor_responses(self):
        print("Listening for response CAN messages...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg and msg.arbitration_id == self.RESPONSE_ID:
                    signals = self.parse_response_frame(msg.data)
                    if signals:
                        print("\nReceived Response Signals (Raw):")
                        for light_id, status_code in signals.items():
                            print(f"ID: {hex(light_id)}, Status: {hex(status_code)}")
                            if status_code not in [0, 1]:
                                print(f"Warning: Unexpected status code {hex(status_code)} for ID {hex(light_id)}")
                        self.write_response_to_file(signals)
                    else:
                        print(f"Invalid response data: {msg.data.hex()}")
        except Exception as e:
            print(f"Response monitoring error: {e}")
    
    def start_response_monitor(self):
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
                                        # Only process if status has changed
                                        if self.last_processed_status[light] != status:
                                            self.last_modified_light = (light, LIGHT_IDS[light])
                                            self.send_can_message(light, status)
                                            self.last_processed_status[light] = status
                                            print(f"Processed status change for {light}: {status}")
                                        else:
                                            print(f"No change in {light} status: {status}, skipping")
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
        if self.db_connection and self.db_connection.is_connected():
            self.db_cursor.close()
            self.db_connection.close()
            print("MySQL connection closed")
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        print("Shutdown complete")

if __name__ == "__main__":
    master = CANLightMaster("analysis_results.txt")
    master.monitor_file()