import can
import time
import os
import threading
from datetime import datetime
import mysql.connector
from mysql.connector import Error

# CAN IDs for each window type
WINDOW_IDS = {
    "DR": 0x201,
    "PS": 0x202,
    "DRS": 0x203,
    "PRS": 0x204
}

# Response IDs (same as window IDs for two-way communication)
RESPONSE_IDS = {
    "DR": 0x201,
    "PS": 0x202,
    "DRS": 0x203,
    "PRS": 0x204
}

# Result codes mapping
RESULT_CODES = ["OP", "CL", "OPG", "CLG", "FOP", "OP_S", "CL_S", "OPG_S", "CLG_S", "FOP_S", "FAILED"]

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

class CANWindowMaster:
    def __init__(self, filename):
        self.filename = filename
        self.channel = 'can0'
        self.bustype = 'socketcan'
        self.bus = None
        self.last_size = os.path.getsize(filename)
        self.running = True
        self.db_connection = None
        self.db_cursor = None
        self.last_processed_status = {window: None for window in WINDOW_IDS}
        
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
    
    def send_can_message(self, window, result, level, level_type, mode):
        try:
            result_index = RESULT_CODES.index(result)
            msg_data = [result_index, level, LEVEL_TYPES.index(level_type), MODES.index(mode.upper())]
            
            msg = can.Message(
                arbitration_id=WINDOW_IDS[window],
                data=msg_data,
                is_extended_id=False
            )
            self.bus.send(msg)
            print(f"Sent: {window} | {result} | {level}% | {level_type} | {mode} (ID: {hex(WINDOW_IDS[window])}, Data: {msg_data})")
        except Exception as e:
            print(f"Error sending CAN message: {e}")
    
    def parse_response_frame(self, msg):
        """Parse response CAN message from slave"""
        try:
            window = next((name for name, can_id in RESPONSE_IDS.items() if can_id == msg.arbitration_id), None)
            if window and len(msg.data) >= 2:
                result = RESULT_CODES[msg.data[0]]
                level = msg.data[1]
                level_type = LEVEL_TYPES[msg.data[2]] if len(msg.data) > 2 else "AUTO"
                mode = MODES[msg.data[3]] if len(msg.data) > 3 else "WHONEN"
                
                return {
                    window: {
                        "result": result,
                        "level": level,
                        "level_type": level_type,
                        "mode": mode
                    }
                }
        except (IndexError, ValueError) as e:
            print(f"Error parsing response: {e}")
        return None
    
    def write_response_to_file(self, status):
        """Write response status to window_response.txt"""
        try:
            with open("window_response.txt", 'a') as f:
                for window, data in status.items():
                    f.write(f"{window} | {data['result']} | {data['level']} | {data['level_type']} | {data['mode']}\n")
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
        """Monitor CAN bus for response messages from slave"""
        print("Listening for response CAN messages...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg and msg.arbitration_id in RESPONSE_IDS.values():
                    status = self.parse_response_frame(msg)
                    if status:
                        print("\nReceived Window Status:")
                        for window, data in status.items():
                            print(f"{window}: {data['result']} | {data['level']}% | {data['level_type']} | {data['mode']}")
                        self.write_response_to_file(status)
                        self.update_database(status)
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
                        
                        for line in new_content.split('\n'):
                            if line.strip() and line.startswith("Window:"):
                                try:
                                    # Split and clean all parts
                                    parts = [p.strip() for p in line.split('|')]
                                    if len(parts) < 5:
                                        print(f"Skipping incomplete line: {line}")
                                        continue
                                        
                                    window = parts[0].split(':')[1].strip()
                                    result = parts[1].split(':')[1].strip()
                                    level = int(parts[2].split(':')[1].strip().replace('%', ''))
                                    level_type = parts[3].split(':')[1].strip().upper()
                                    mode = parts[4].split(':')[1].strip().upper()
                                    
                                    # Validate window
                                    if window not in WINDOW_IDS:
                                        print(f"Invalid window: {window}")
                                        continue
                                        
                                    # Validate result
                                    if result not in RESULT_CODES:
                                        print(f"Invalid result: {result}")
                                        continue
                                        
                                    # Validate level
                                    if not 0 <= level <= 100:
                                        print(f"Invalid level: {level}")
                                        continue
                                        
                                    # Validate level_type
                                    if level_type not in LEVEL_TYPES:
                                        print(f"Invalid level_type: {level_type}")
                                        continue
                                        
                                    # Validate mode (case insensitive)
                                    if mode.upper() not in [m.upper() for m in MODES]:
                                        print(f"Invalid mode: {mode}")
                                        continue
                                        
                                    # Convert mode to standard case
                                    mode = MODES[[m.upper() for m in MODES].index(mode.upper())]
                                    
                                    self.send_can_message(window, result, level, level_type, mode)
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
    master = CANWindowMaster("windows_analysis.txt")
    master.monitor_file()