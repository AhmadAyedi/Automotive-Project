import serial
import time
import os
import threading
from datetime import datetime
import mysql.connector
from mysql.connector import Error

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

# Status codes for LIN communication
STATUS_CODES = {
    "ACTIVATED": 0x01,
    "DEACTIVATED": 0x00,
    "FAILED": 0xFF,
    "INVALID": 0xFE
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
WAKEUP_PIN = 1
SYNC_BYTE = 0x55
BREAK_BYTE = 0x00

class LINLightMaster:
    def __init__(self, filename):
        self.filename = filename
        self.last_size = os.path.getsize(filename)
        self.running = True
        self.last_modified_light = None
        self.last_processed_status = {light: None for light in LIGHT_IDS}
        
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
    
    def send_light_command(self, light, status):
        """Send a LIN frame to control a specific light"""
        try:
            self.wakeup_slave()
            self.send_break()
            
            self.ser.write(bytes([SYNC_BYTE]))
            pid = self.calculate_pid(LIGHT_IDS[light])
            self.ser.write(bytes([pid]))
            
            data = bytes([STATUS_CODES[status]])
            self.ser.write(data)
            
            checksum = self.calculate_checksum(pid, data)
            self.ser.write(bytes([checksum]))
            self.ser.flush()
            
            print(f"Sent LIN frame: {light} - {status} (ID: {hex(LIGHT_IDS[light])}, Data: {hex(STATUS_CODES[status])})")
            self.last_modified_light = (light, LIGHT_IDS[light])
            
        except Exception as e:
            print(f"Error sending LIN message: {e}")
    
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
    
    def parse_response_frame(self, data):
        """Parse the response frame from slave (7 bytes - one for each light)"""
        if len(data) != 7:
            print(f"Invalid response frame length: {len(data)} bytes")
            return None
        
        signals = {}
        light_order = [
            0x10,  # Low Beam
            0x11,  # High Beam
            0x12,  # Parking Left
            0x13,  # Parking Right
            0x14,  # Hazard Lights
            0x15,  # Right Turn
            0x16   # Left Turn
        ]
        
        for i, light_id in enumerate(light_order):
            signals[light_id] = data[i]
        return signals
    
    def write_response_to_file(self, signals):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            with open("lighting_response.txt", 'a') as f:
                for light_id, status_code in signals.items():
                    light_name = next((k for k, v in LIGHT_IDS.items() if v == light_id), f"Unknown ID: {hex(light_id)}")
                    status_name = "ON" if status_code == 1 else "OFF"
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
                                data_length = 7  # Our status response is 7 bytes
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
                                            print("\nReceived Response Signals (Raw):")
                                            for light_id, status_code in signals.items():
                                                print(f"ID: {hex(light_id)}, Status: {hex(status_code)}")
                                            self.write_response_to_file(signals)
                                    else:
                                        print(f"Checksum mismatch: received {hex(checksum)}, calculated {hex(calc_checksum)}")
                                    
                                    buffer = bytes()  # Clear buffer after processing
                time.sleep(0.001)
                
        except Exception as e:
            print(f"Response monitoring error: {e}")
    
    def start_response_monitor(self):
        self.response_thread = threading.Thread(target=self.monitor_responses, daemon=True)
        self.response_thread.start()
    
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
                        
                        lines = new_content.split('\n')
                        for line in lines:
                            if line.strip() and line.startswith("Light:") and "Result:" in line:
                                try:
                                    parts = line.split('|')
                                    light = parts[0].split(':')[1].strip()
                                    status = parts[1].split(':')[1].strip().upper()  # Convert to uppercase
                                    
                                    if light in LIGHT_IDS and status in STATUS_CODES:
                                        if self.last_processed_status[light] != status:
                                            self.send_light_command(light, status)
                                            self.last_processed_status[light] = status
                                            print(f"Processed status change for {light}: {status}")
                                            
                                            # Request updated status after sending command
                                            time.sleep(0.1)
                                            self.request_status_report()
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
        if self.ser:
            self.ser.close()
        if self.db_connection and self.db_connection.is_connected():
            self.db_cursor.close()
            self.db_connection.close()
            print("MySQL connection closed")
        GPIO.cleanup()
        print("Shutdown complete")

if __name__ == "__main__":
    import RPi.GPIO as GPIO
    master = LINLightMaster("analysis_results.txt")
    master.monitor_file()