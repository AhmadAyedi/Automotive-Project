import serial
import time
import os
import threading
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import RPi.GPIO as GPIO

# LIN Frame IDs for each light type
LIGHT_IDS = {
    "Low Beam": 0x10,
    "High Beam": 0x11,
    "Parking Left": 0x12,
    "Parking Right": 0x13,
    "Hazard Lights": 0x14,
    "Right Turn": 0x15,
    "Left Turn": 0x16
}

# Response IDs (same as light IDs for two-way communication)
RESPONSE_IDS = {
    "Low Beam": 0x10,
    "High Beam": 0x11,
    "Parking Left": 0x12,
    "Parking Right": 0x13,
    "Hazard Lights": 0x14,
    "Right Turn": 0x15,
    "Left Turn": 0x16
}

# Status codes for LIN communication
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
    0x10: 5,  # Low Beam
    0x11: 6,  # High Beam
    0x12: 3,  # Parking Left
    0x13: 4,  # Parking Right
    0x14: 7,  # Hazard Lights
    0x15: 9,  # Right Turn
    0x16: 8   # Left Turn
}

# LIN Constants
SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 19200
WAKEUP_PIN = 4
SYNC_BYTE = 0x55
BREAK_BYTE = 0x00

class LINLightMaster:
    def __init__(self, filename):
        self.filename = filename
        self.last_size = os.path.getsize(filename)
        self.running = True
        self.db_connection = None
        self.db_cursor = None
        self.last_modified_light = None
        self.last_processed_status = {light: None for light in LIGHT_IDS}
        self.last_processed_mode = {light: None for light in LIGHT_IDS}
        
        # Initialize GPIO and serial
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(WAKEUP_PIN, GPIO.OUT)
        GPIO.output(WAKEUP_PIN, GPIO.HIGH)
        
        self.ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=0)
        self.init_db_connection()
        self.start_response_monitor()
    
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
    
    def calculate_pid(self, frame_id):
        if frame_id > 0x3F:
            raise ValueError("Frame ID must be 6 bits (0-63)")
        p0 = (frame_id ^ (frame_id >> 1) ^ (frame_id >> 2) ^ (frame_id >> 4)) & 0x01
        p1 = ~((frame_id >> 1) ^ (frame_id >> 3) ^ (frame_id >> 4) ^ (frame_id >> 5)) & 0x01
        return (frame_id & 0x3F) | (p0 << 6) | (p1 << 7)
    
    def calculate_checksum(self, pid, data):
        checksum = pid
        for byte in data:
            checksum += byte
            if checksum > 0xFF:
                checksum -= 0xFF
        return (0xFF - checksum) & 0xFF
    
    def send_break(self):
        self.ser.baudrate = BAUD_RATE // 4
        self.ser.write(bytes([BREAK_BYTE]))
        self.ser.flush()
        time.sleep(13 * (1.0 / (BAUD_RATE // 4)))
        self.ser.baudrate = BAUD_RATE
    
    def wakeup_slave(self):
        GPIO.output(WAKEUP_PIN, GPIO.LOW)
        time.sleep(0.01)
        GPIO.output(WAKEUP_PIN, GPIO.HIGH)
    
    def send_light_command(self, light, status, mode):
        """Send a LIN frame to control a specific light with status and mode"""
        try:
            self.wakeup_slave()
            self.send_break()
            
            self.ser.write(bytes([SYNC_BYTE]))
            pid = self.calculate_pid(LIGHT_IDS[light])
            self.ser.write(bytes([pid]))
            
            data = bytes([STATUS_CODES[status], MODE_CODES[mode]])
            self.ser.write(data)
            
            checksum = self.calculate_checksum(pid, data)
            self.ser.write(bytes([checksum]))
            self.ser.flush()
            
            print(f"Sent LIN frame: {light} - {status} - {mode} (ID: {hex(LIGHT_IDS[light])}, Data: {[hex(STATUS_CODES[status]), hex(MODE_CODES[mode])]})")
            self.last_modified_light = (light, LIGHT_IDS[light])
            
        except Exception as e:
            print(f"Error sending LIN message: {e}")
    
    def parse_response_frame(self, data):
        """Parse the response frame from slave (2 bytes per light - status and mode)"""
        if len(data) != 14:  # 7 lights * 2 bytes each
            print(f"Invalid response frame length: {len(data)} bytes")
            return None
        
        signals = {}
        light_order = [
            "Low Beam", "High Beam", "Parking Left", "Parking Right",
            "Hazard Lights", "Right Turn", "Left Turn"
        ]
        
        for i, light in enumerate(light_order):
            status_code = data[i*2]
            mode_code = data[i*2 + 1]
            signals[light] = {
                "status": STATUS_NAMES.get(status_code, f"Unknown: {hex(status_code)}"),
                "mode": MODE_NAMES.get(mode_code, f"Unknown: {hex(mode_code)}")
            }
        return signals
    
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
        """Update the database with light status"""
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
        """Monitor for response frames from slave"""
        print("Listening for response LIN messages...")
        buffer = bytes()
        
        try:
            while self.running:
                if self.ser.in_waiting:
                    byte = self.ser.read(1)
                    buffer += byte
                    
                    # Check for break character (start of LIN frame)
                    if byte == bytes([BREAK_BYTE]):
                        buffer = bytes([BREAK_BYTE])  # Start fresh frame
                        continue
                        
                    # Only proceed if we have break + sync
                    if len(buffer) >= 2 and buffer[0] == BREAK_BYTE and buffer[1] == SYNC_BYTE:
                        if len(buffer) >= 3:
                            pid_byte = buffer[2]
                            frame_id = pid_byte & 0x3F
                            
                            # Check if this is a status response (ID 0x18)
                            if frame_id == 0x18:
                                data_length = 14  # 7 lights * 2 bytes each
                                total_length = 3 + data_length + 1  # Break+Sync+PID + data + checksum
                                
                                # Read remaining bytes if needed
                                while len(buffer) < total_length and self.running:
                                    if self.ser.in_waiting:
                                        buffer += self.ser.read(1)
                                    time.sleep(0.001)
                                
                                if len(buffer) >= total_length:
                                    data = buffer[3:3+data_length]
                                    checksum = buffer[3+data_length]
                                    
                                    # Verify checksum
                                    calc_checksum = self.calculate_checksum(pid_byte, data)
                                    if checksum == calc_checksum:
                                        signals = self.parse_response_frame(data)
                                        if signals:
                                            print("\nReceived Response Signals:")
                                            for light, data in signals.items():
                                                print(f"{light}: {data['status']} | {data['mode']}")
                                            self.write_response_to_file(signals)
                                            self.update_database(signals)
                                    else:
                                        print(f"Checksum mismatch: received {hex(checksum)}, calculated {hex(calc_checksum)}")
                                    
                                    buffer = bytes()  # Clear buffer after processing
                time.sleep(0.001)
                
        except Exception as e:
            print(f"Response monitoring error: {e}")
    
    def start_response_monitor(self):
        self.response_thread = threading.Thread(target=self.monitor_responses, daemon=True)
        self.response_thread.start()
    
    def request_status_report(self):
        """Send a LIN frame to request status report from slave"""
        try:
            self.wakeup_slave()
            self.send_break()
            
            self.ser.write(bytes([SYNC_BYTE]))
            pid = self.calculate_pid(0x17)  # Special ID for status request
            self.ser.write(bytes([pid]))
            
            checksum = self.calculate_checksum(pid, bytes())
            self.ser.write(bytes([checksum]))
            self.ser.flush()
            
            print("Sent status request frame")
            
        except Exception as e:
            print(f"Error sending status request: {e}")
    
    def monitor_file(self):
        print(f"Monitoring {self.filename} for new light status updates...")
        print("Add new lines to the file to send LIN messages")
        
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
                                            
                                            self.send_light_command(light, status, mode)
                                            self.last_processed_status[light] = status
                                            self.last_processed_mode[light] = mode
                                            print(f"Processed status/mode change for {light}: {status}/{mode}")
                                            
                                            # Request updated status after sending command
                                            time.sleep(0.1)
                                            self.request_status_report()
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
        if self.ser:
            self.ser.close()
        if self.db_connection and self.db_connection.is_connected():
            self.db_cursor.close()
            self.db_connection.close()
            print("MySQL connection closed")
        GPIO.cleanup()
        print("Shutdown complete")

if __name__ == "__main__":
    master = LINLightMaster("analysis_results.txt")
    master.monitor_file()