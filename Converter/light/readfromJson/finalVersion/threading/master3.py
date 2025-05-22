import can
import time
import os
import threading
import json
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

# Status codes for CAN communication (1 byte) - Using uppercase keys to match input file
STATUS_CODES = {
    "ACTIVATED": 0x01,
    "DEACTIVATED": 0x00,
    "FAILED": 0xFF,
    "INVALID": 0xFE
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
    0x01: "ON",
    0x00: "OFF",
    0xFF: "FAILED",
    0xFE: "INVALID"
}

class VehicleLightingSystem:
    # Constants for modes
    PARKEN = "P"       # Parking mode
    STANDBY = "S"      # Standby mode
    WOHNEN = "W"       # Wohnen mode
    FAHREN = "F"       # Fahren mode
   
    ON = "ON"
    OFF = "OFF"

    def __init__(self):
        self.current_mode = self.PARKEN
        self.low_beam = self.OFF
        self.high_beam = self.OFF
        self.parking_left = self.OFF
        self.parking_right = self.OFF
        self.hazard_lights = self.OFF
        self.right_turn = self.OFF
        self.left_turn = self.OFF
        self.previous_mode = None
        self.mode_sequence = [self.PARKEN, self.STANDBY, self.WOHNEN, self.FAHREN]

    def set_initial_parken_state(self):
        self.current_mode = self.PARKEN
        self.low_beam = self.OFF
        self.high_beam = self.OFF
        self.parking_left = self.OFF
        self.parking_right = self.OFF
        self.hazard_lights = self.OFF
        self.right_turn = self.OFF
        self.left_turn = self.OFF
        self.previous_mode = None

    def set_low_beam(self, new_mode):
        self.current_mode = new_mode
        if new_mode in [self.WOHNEN, self.FAHREN]:
            self.low_beam = self.ON
        elif new_mode in [self.PARKEN, self.STANDBY]:
            self.low_beam = self.OFF
        return self.low_beam

    def set_high_beam(self, new_mode):
        self.current_mode = new_mode
        self.high_beam = self.ON  # Always ON regardless of mode
        return self.high_beam

    def set_parking_lights(self, new_mode):
        self.current_mode = new_mode
        if new_mode in [self.PARKEN, self.STANDBY, self.WOHNEN]:
            self.parking_left = self.ON
            self.parking_right = self.ON
        elif new_mode == self.FAHREN:
            self.parking_left = self.OFF
            self.parking_right = self.OFF
        return (self.parking_left, self.parking_right)

    def set_hazard_lights(self, new_mode):
        self.current_mode = new_mode
        if new_mode in [self.FAHREN, self.WOHNEN]:
            self.hazard_lights = self.ON
        else:  # PARKEN and STANDBY
            self.hazard_lights = self.OFF
        return self.hazard_lights

    def set_turn_signals(self, new_mode):
        self.current_mode = new_mode
        if new_mode in [self.WOHNEN, self.FAHREN]:
            self.right_turn = self.ON
            self.left_turn = self.ON
        elif new_mode in [self.PARKEN, self.STANDBY]:
            self.right_turn = self.OFF
            self.left_turn = self.OFF
        return (self.right_turn, self.left_turn)

class CANLightMaster:
    def __init__(self, json_filename):
        self.json_filename = json_filename
        self.analysis_filename = "analysis_results.txt"
        self.channel = 'can0'
        self.bus = None
        self.running = True
        self.RESPONSE_ID = 0x200
        self.db_connection = None
        self.db_cursor = None
        self.last_modified_light = None
        self.last_processed_status = {light: None for light in LIGHT_IDS}
        
        # Initialize analysis file
        self.initialize_analysis_file()
        
        self.init_can_bus()
        self.init_db_connection()
        self.start_response_monitor()
    
    def parse_message_catalog(self, filename):
        """Extracts light status from message_catalog.json"""
        light_status = {
            'Low Beam': None,
            'High Beam': None,
            'Hazard Lights': None,
            'Left Turn': None,
            'Right Turn': None,
            'break_light': None
        }
        
        try:
            with open(filename, 'r') as file:
                data = json.load(file)
                
                # Find the LightsStatus service
                for service in data['services']:
                    if service['service_name'] == "LightsStatus":
                        for event in service['events']:
                            status = "ON" if event['event_value']['status'] == "1" else "OFF"
                            
                            if event['event_name'] == "Low_Beam_HeadlightStatus":
                                light_status['Low Beam'] = status
                            elif event['event_name'] == "High_Beam_HeadlightStatus":
                                light_status['High Beam'] = status
                            elif event['event_name'] == "HazardStatus":
                                light_status['Hazard Lights'] = status
                            elif event['event_name'] == "LeftTurnStatus":
                                light_status['Left Turn'] = status
                            elif event['event_name'] == "RightTurnStatus":
                                light_status['Right Turn'] = status
                            elif event['event_name'] == "BreakLightStatus":
                                light_status['break_light'] = status
                        break
                        
        except Exception as e:
            print(f"Error reading JSON file: {e}")
        
        return light_status

    def analyze_lights(self, light_status):
        system = VehicleLightingSystem()
        system.set_initial_parken_state()
        
        results = []
        
        # Low Beam analysis
        if light_status['Low Beam'] is not None:
            expected_status = system.set_low_beam(system.PARKEN)
            result = "ACTIVATED" if light_status['Low Beam'] == "ON" else "DEACTIVATED"
            results.append(f"Light: Low Beam | Result: {result}")
        
        # High Beam analysis
        if light_status['High Beam'] is not None:
            expected_status = system.set_high_beam(system.PARKEN)
            result = "ACTIVATED" if light_status['High Beam'] == expected_status else "DEACTIVATED"
            results.append(f"Light: High Beam | Result: {result}")
        
        # Hazard Lights analysis
        if light_status['Hazard Lights'] is not None:
            expected_status = system.set_hazard_lights(system.PARKEN)
            result = "ACTIVATED" if light_status['Hazard Lights'] == "ON" else "DEACTIVATED"
            results.append(f"Light: Hazard Lights | Result: {result}")
        
        # Turn Signals analysis
        if light_status['Left Turn'] is not None:
            _, expected_left = system.set_turn_signals(system.PARKEN)
            result = "ACTIVATED" if light_status['Left Turn'] == "ON" else "DEACTIVATED"
            results.append(f"Light: Left Turn | Result: {result}")
        
        if light_status['Right Turn'] is not None:
            expected_right, _ = system.set_turn_signals(system.PARKEN)
            result = "ACTIVATED" if light_status['Right Turn'] == "ON" else "DEACTIVATED"
            results.append(f"Light: Right Turn | Result: {result}")
        
        # Parking Lights (not in JSON, but keeping for compatibility)
        parking_left, parking_right = system.set_parking_lights(system.PARKEN)
        results.append(f"Light: Parking Left | Result: DEACTIVATED")
        results.append(f"Light: Parking Right | Result: DEACTIVATED")
        
        return results

    def initialize_analysis_file(self):
        """Initialize the analysis file with current JSON data"""
        # Initialize results file with a header only if it doesn't exist
        if not os.path.exists(self.analysis_filename):
            with open(self.analysis_filename, "w") as f:
                f.write("Vehicle Lighting System Analysis Results\n")
        
        print(f"Initial analysis of {self.json_filename}...")
        light_status = self.parse_message_catalog(self.json_filename)
        if any(light_status.values()):
            print("\n=== Initial Analysis ===")
            results = self.analyze_lights(light_status)
            for line in results:
                print(line)
            
            with open(self.analysis_filename, "a") as f:
                for line in results:
                    f.write(line + "\n")
        else:
            print("No light status information found in the JSON file.")
    
    def monitor_json_file(self):
        """Continuously monitors the JSON file for changes"""
        print(f"\nStarting real-time monitoring of: {self.json_filename}")
        print("\nLighting System Requirements Summary:")
        print("- Low Beam: ON in Wohnen/Fahren, OFF in Parking/Standby")
        print("- High Beam: ON in all modes")
        print("- Hazard Lights: ON in Fahren/Wohnen, OFF in Parking/Standby")
        print("- Turn Signals: ON in Wohnen/Fahren, OFF in Parking/Standby")
        
        last_modified = 0
        last_content_hash = None
        
        try:
            while self.running:
                current_modified = os.path.getmtime(self.json_filename)
                if current_modified > last_modified:
                    last_modified = current_modified
                    
                    light_status = self.parse_message_catalog(self.json_filename)
                    current_hash = str(light_status)
                    
                    if current_hash != last_content_hash:
                        last_content_hash = current_hash
                        results = self.analyze_lights(light_status)
                        
                        print("\nNew entries detected:")
                        for line in results:
                            print(line)
                        
                        with open(self.analysis_filename, "a") as f:
                            for line in results:
                                f.write(line + "\n")
                        
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nJSON monitoring stopped.")
    
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
                host="192.168.1.15",
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
        
        try:
            with open("lighting_response.txt", 'a') as f:
                for light_id, status_code in signals.items():
                    light_name = LIGHT_NAMES.get(light_id, f"Unknown ID: {hex(light_id)}")
                    status_name = STATUS_NAMES.get(status_code, f"Unknown status: {hex(status_code)}")
                    f.write(f"{light_name} = {status_name}\n")
                f.write("\n")
            print(f"Response written to lighting_response.txt at {timestamp}")
        except Exception as e:
            print(f"Error writing to lighting_response.txt: {e}")
        
        try:
            if not self.db_connection.is_connected():
                self.init_db_connection()
            
            if self.last_modified_light:
                light_name, light_id = self.last_modified_light
                status_code = signals.get(light_id, 0)
                new_message = 1 if status_code == 1 else 0
                
                select_query = "SELECT message FROM protocol_data WHERE event_id = %s"
                self.db_cursor.execute(select_query, (EVENT_IDS[light_id],))
                result = self.db_cursor.fetchone()
                
                if result:
                    current_message = result[0]
                    if current_message != new_message:
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
                            if status_code not in [0, 1, 0xFF, 0xFE]:
                                print(f"Warning: Unexpected status code {hex(status_code)} for ID {hex(light_id)}")
                        self.write_response_to_file(signals)
                    else:
                        print(f"Invalid response data: {msg.data.hex()}")
        except Exception as e:
            print(f"Response monitoring error: {e}")
    
    def start_response_monitor(self):
        self.response_thread = threading.Thread(target=self.monitor_responses, daemon=True)
        self.response_thread.start()
    
    def monitor_analysis_file(self):
        print(f"Monitoring {self.analysis_filename} for new light status updates...")
        print("Press Ctrl+C to stop monitoring...")
        
        last_size = os.path.getsize(self.analysis_filename)
        
        try:
            while self.running:
                current_size = os.path.getsize(self.analysis_filename)
                
                if current_size > last_size:
                    with open(self.analysis_filename, 'r') as f:
                        f.seek(last_size)
                        new_content = f.read()
                        last_size = current_size
                        
                        lines = new_content.split('\n')
                        for line in lines:
                            if line.strip() and line.startswith("Light:") and "Result:" in line:
                                try:
                                    parts = line.split('|')
                                    light = parts[0].split(':')[1].strip()
                                    status = parts[1].split(':')[1].strip().upper()  # Convert to uppercase
                                    
                                    if light in LIGHT_IDS and status in STATUS_CODES:
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
    # Create the master with the JSON filename
    master = CANLightMaster("message_catalog.json")
    
    # Start threads for monitoring both JSON and analysis files
    json_monitor_thread = threading.Thread(target=master.monitor_json_file, daemon=True)
    json_monitor_thread.start()
    
    # Monitor the analysis file in the main thread
    master.monitor_analysis_file()