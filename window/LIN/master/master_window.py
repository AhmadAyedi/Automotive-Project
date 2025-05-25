import serial
import time
import os
import threading
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import RPi.GPIO as GPIO

# LIN Frame IDs for each window type
WINDOW_IDS = {
    "DR": 0x10,
    "PS": 0x11,
    "DRS": 0x12,
    "PRS": 0x13
}

# Response IDs (same as window IDs for two-way communication)
RESPONSE_IDS = {
    0x10: "DR",
    0x11: "PS",
    0x12: "DRS",
    0x13: "PRS"
}

# Result codes mapping
RESULT_CODES = ["OP", "CL", "OPG", "CLG", "FOP", "OP_D", "CL_D", "OPG_D", "CLG_D", "FOP_D", 
                "OP_AD", "CL_AD", "OPG_AD", "CLG_AD", "FOP_AD", "OP_A", "CL_A", "OPG_A", "CLG_A", "FOP_A", "FAILED"]

# Database event IDs for each window
EVENT_IDS = {
    "DR": 21,
    "PS": 23,
    "DRS": 22,
    "PRS": 24
}

# Valid level types and modes
LEVEL_TYPES = ["AUTO", "MANUAL"]
MODES = ["WHONEN", "FAHREN"]

# LIN Constants
SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 19200
WAKEUP_PIN = 1
SYNC_BYTE = 0x55
BREAK_BYTE = 0x00

class LINWindowMaster:
    def __init__(self, filename):
        self.filename = filename
        self.last_size = os.path.getsize(filename)
        self.running = True
        self.last_processed_status = {window: None for window in WINDOW_IDS}
        
        # Initialize GPIO and serial
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(WAKEUP_PIN, GPIO.OUT)
        GPIO.output(WAKEUP_PIN, GPIO.HIGH)
        
        self.ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=0.1)
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
            
            required_ids = {21, 23, 22, 24}
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
                print(f"Initialized {len(missing_ids)} missing window rows in protocol_data")
            
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
    
    def send_window_command(self, window, result, level, level_type, mode, safety):
        """Send a LIN frame to control a window"""
        try:
            self.wakeup_slave()
            self.send_break()
            
            self.ser.write(bytes([SYNC_BYTE]))
            pid = self.calculate_pid(WINDOW_IDS[window])
            self.ser.write(bytes([pid]))
            
            result_index = RESULT_CODES.index(result)
            msg_data = bytes([
                result_index,
                level,
                LEVEL_TYPES.index(level_type),
                MODES.index(mode.upper()),
                1 if safety == "ON" else 0
            ])
            
            self.ser.write(msg_data)
            checksum = self.calculate_checksum(pid, msg_data)
            self.ser.write(bytes([checksum]))
            self.ser.flush()
            
            print(f"Sent LIN frame: {window} | {result} | {level}% | {level_type} | {mode} | safety_{safety}")
            
        except Exception as e:
            print(f"Error sending LIN message: {e}")
    
    def parse_response_frame(self, buffer):
        """Parse response frame from slave"""
        try:
            # Frame structure: [BREAK, SYNC, PID, DATA(5), CHECKSUM]
            if len(buffer) < 9:
                return None
            
            # Verify break and sync bytes
            if buffer[0] != BREAK_BYTE or buffer[1] != SYNC_BYTE:
                return None
            
            pid = buffer[2]
            data = buffer[3:8]
            received_checksum = buffer[8]
            
            # Verify checksum
            calc_checksum = self.calculate_checksum(pid, data)
            if received_checksum != calc_checksum:
                print(f"Checksum mismatch: received {hex(received_checksum)}, calculated {hex(calc_checksum)}")
                return None
            
            frame_id = pid & 0x3F
            window = RESPONSE_IDS.get(frame_id)
            
            if not window:
                print(f"Unknown response frame ID: {frame_id}")
                return None
            
            result = RESULT_CODES[data[0]]
            level = data[1]
            level_type = LEVEL_TYPES[data[2]] if data[2] < len(LEVEL_TYPES) else "AUTO"
            mode = MODES[data[3]] if data[3] < len(MODES) else "WHONEN"
            safety = "ON" if data[4] == 1 else "OFF"
            
            return {
                window: {
                    "result": result,
                    "level": level,
                    "level_type": level_type,
                    "mode": mode,
                    "safety": safety
                }
            }
            
        except (IndexError, ValueError) as e:
            print(f"Error parsing response frame: {e}")
            return None
    
    def write_response_to_file(self, status):
        """Write response status to window_response.txt"""
        try:
            with open("window_response.txt", 'a') as f:
                for window, data in status.items():
                    f.write(f"{window} | {data['result']} | {data['level']} | {data['level_type']} | {data['mode']} | safety_{data['safety']}\n")
            print("Response status written to window_response.txt")
        except Exception as e:
            print(f"Error writing to window_response.txt: {e}")
    
    def update_database(self, status):
        """Update the database with window status levels"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            if not self.db_connection.is_connected():
                self.init_db_connection()
            
            update_query = """
            UPDATE protocol_data
            SET message = %s, timestamp = %s
            WHERE event_id = %s
            """
            
            for window, data in status.items():
                level = data['level']
                event_id = EVENT_IDS[window]
                
                if self.last_processed_status[window] != level:
                    self.db_cursor.execute(update_query, (level, timestamp, event_id))
                    print(f"Updated MySQL database: event_id={event_id} ({window}), message={level} at {timestamp}")
                    self.last_processed_status[window] = level
            
            self.db_connection.commit()
            
        except Error as e:
            print(f"Error updating MySQL database: {e}")
            if not self.db_connection.is_connected():
                print("Database connection lost; will attempt to reconnect on next update")
    
    def monitor_responses(self):
        """Monitor for response frames from slave"""
        print("Listening for response LIN messages...")
        buffer = bytearray()
        
        try:
            while self.running:
                if self.ser.in_waiting:
                    byte = self.ser.read(1)
                    if byte:
                        buffer += byte
                    
                    # Process complete frames in buffer
                    while len(buffer) >= 9:
                        status = self.parse_response_frame(buffer[:9])
                        if status:
                            print("\nReceived Window Status:")
                            for window, data in status.items():
                                print(f"{window}: {data['result']} | {data['level']}% | {data['level_type']} | {data['mode']} | safety_{data['safety']}")
                            self.write_response_to_file(status)
                            self.update_database(status)
                        
                        # Remove processed bytes from buffer
                        buffer = buffer[9:]
                
                time.sleep(0.001)
                
        except Exception as e:
            print(f"Response monitoring error: {e}")
        finally:
            self.ser.close()
    
    def start_response_monitor(self):
        """Start a thread to monitor response messages"""
        self.response_thread = threading.Thread(target=self.monitor_responses, daemon=True)
        self.response_thread.start()
    
    def monitor_file(self):
        print(f"Monitoring {self.filename} for new window status updates...")
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
                            if line.strip() and line.startswith("Window:"):
                                try:
                                    parts = [p.strip() for p in line.split('|')]
                                    if len(parts) < 6:
                                        print(f"Skipping incomplete line: {line}")
                                        continue
                                        
                                    window = parts[0].split(':')[1].strip()
                                    result = parts[1].split(':')[1].strip()
                                    level = int(parts[2].split(':')[1].strip().replace('%', ''))
                                    level_type = parts[3].split(':')[1].strip().upper()
                                    mode = parts[4].split(':')[1].strip().upper()
                                    safety = parts[5].split(':')[1].strip().upper()
                                    
                                    if window not in WINDOW_IDS:
                                        print(f"Invalid window: {window}")
                                        continue
                                        
                                    if result not in RESULT_CODES:
                                        print(f"Invalid result: {result}")
                                        continue
                                        
                                    if not 0 <= level <= 100:
                                        print(f"Invalid level: {level}")
                                        continue
                                        
                                    if level_type not in LEVEL_TYPES:
                                        print(f"Invalid level_type: {level_type}")
                                        continue
                                        
                                    if mode.upper() not in [m.upper() for m in MODES]:
                                        print(f"Invalid mode: {mode}")
                                        continue
                                        
                                    if safety not in ["ON", "OFF"]:
                                        print(f"Invalid safety value: {safety}")
                                        continue
                                    
                                    mode = MODES[[m.upper() for m in MODES].index(mode.upper())]
                                    
                                    self.send_window_command(window, result, level, level_type, mode, safety)
                                except (IndexError, ValueError) as e:
                                    print(f"Malformed line: {line} - Error: {e}")
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        self.running = False
        if hasattr(self, 'response_thread') and self.response_thread.is_alive():
            self.response_thread.join(timeout=0.5)
        if self.ser and self.ser.is_open:
            self.ser.close()
        if hasattr(self, 'db_connection') and self.db_connection.is_connected():
            self.db_cursor.close()
            self.db_connection.close()
            print("MySQL connection closed")
        GPIO.cleanup()
        print("Shutdown complete")

if __name__ == "__main__":
    master = LINWindowMaster("windows_analysis.txt")
    master.monitor_file()