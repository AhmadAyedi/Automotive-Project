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

# Response ID for slave responses
RESPONSE_ID = 0x300

# Result codes mapping
RESULT_CODES = ["OP", "CL", "OPG", "CLG", "FOP", "OP_S", "CL_S", "OPG_S", "CLG_S", "FOP_S"]

# Database event IDs for each window
EVENT_IDS = {
    "DR": 1,
    "PS": 2,
    "DRS": 3,
    "PRS": 4
}

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
        self.last_processed_status = {window: None for window in WINDOW_IDS}  # Track last processed status
        
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
            
            # Ensure the protocol_data table exists and has exactly 4 rows for windows
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
            
            # Initialize rows for window event_ids 1, 2, 3, 4 if not present
            required_ids = {1, 2, 3, 4}
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
            
            # Remove any extra rows for windows (optional, if you want to keep only window data)
            # self.db_cursor.execute("DELETE FROM protocol_data WHERE event_id NOT IN (1, 2, 3, 4)")
            # self.db_connection.commit()
            
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            raise
    
    def send_can_message(self, window, result, level):
        try:
            # Pack result index and level into message
            result_index = RESULT_CODES.index(result)
            msg_data = [result_index, level]
            
            msg = can.Message(
                arbitration_id=WINDOW_IDS[window],
                data=msg_data,
                is_extended_id=False
            )
            self.bus.send(msg)
            print(f"Sent: {window} | {result} | {level}% (ID: {hex(WINDOW_IDS[window])}, Data: {msg_data})")
        except Exception as e:
            print(f"Error sending CAN message: {e}")
    
    def parse_response_frame(self, data):
        """Parse response CAN data into window status"""
        if len(data) != 8:  # 2 bytes per window (result + level)
            print(f"Unexpected response length: {len(data)} bytes")
            return None
        
        try:
            status = {
                "DR": {
                    "result": RESULT_CODES[data[0]],
                    "level": data[1]
                },
                "PS": {
                    "result": RESULT_CODES[data[2]],
                    "level": data[3]
                },
                "DRS": {
                    "result": RESULT_CODES[data[4]],
                    "level": data[5]
                },
                "PRS": {
                    "result": RESULT_CODES[data[6]],
                    "level": data[7]
                }
            }
            return status
        except IndexError as e:
            print(f"Error parsing response: {e}")
            return None
    
    def write_response_to_file(self, status):
        """Write response status to window_response.txt"""
        try:
            with open("window_response.txt", 'a') as f:
                for window in ["DR", "PS", "DRS", "PRS"]:
                    f.write(f"{window} | {status[window]['result']} | {status[window]['level']}%\n")
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
            
            for window in ["DR", "PS", "DRS", "PRS"]:
                level = status[window]['level']
                event_id = EVENT_IDS[window]
                
                # Only update if the level has changed
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
                if msg and msg.arbitration_id == RESPONSE_ID:
                    status = self.parse_response_frame(msg.data)
                    if status:
                        print("\nReceived Window Status:")
                        for window in status:
                            print(f"{window}: {status[window]['result']} | {status[window]['level']}%")
                        self.write_response_to_file(status)
                        self.update_database(status)
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
                                    result = parts[1].split(':')[1].strip()
                                    level_part = parts[2].split(':')[1].strip()
                                    level = int(level_part.replace('%', ''))
                                    
                                    if window in WINDOW_IDS and 0 <= level <= 100 and result in RESULT_CODES:
                                        self.send_can_message(window, result, level)
                                    else:
                                        print(f"Ignoring unknown window/level/result: {line}")
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
        if self.db_connection and self.db_connection.is_connected():
            self.db_cursor.close()
            self.db_connection.close()
            print("MySQL connection closed")
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        print("Shutdown complete")

if __name__ == "__main__":
    master = CANWindowMaster("windows_analysis.txt")
    master.monitor_file()