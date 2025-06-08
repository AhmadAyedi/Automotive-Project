#!/usr/bin/env python3
"""
Professional CAN Window Master Controller
Uses DBC file and cantools for CAN communication
Maintains all original functionality with improved protocol handling
"""

import can
import time
import os
import threading
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import cantools

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
        self.last_processed_status = {
            "DR": None, "PS": None, "DRS": None, "PRS": None
        }
        
        # Database event IDs for each window
        self.EVENT_IDS = {
            "DR": 21,
            "PS": 23,
            "DRS": 22,
            "PRS": 24
        }

        # Load DBC file and create message map
        self.db = cantools.database.load_file('window_system.dbc')
        self.message_map = {
            "DR": self.db.get_message_by_name("DR_CTRL"),
            "PS": self.db.get_message_by_name("PS_CTRL"),
            "DRS": self.db.get_message_by_name("DRS_CTRL"),
            "PRS": self.db.get_message_by_name("PRS_CTRL")
        }
        
        self.init_can_bus()
        self.init_db_connection()
        self.start_response_monitor()
    
    def init_can_bus(self):
        """Initialize CAN bus interface"""
        try:
            os.system(f'sudo /sbin/ip link set {self.channel} up type can bitrate 500000')
            time.sleep(0.1)
            self.bus = can.interface.Bus(channel=self.channel, bustype=self.bustype)
            print("CAN bus initialized successfully")
        except Exception as e:
            print(f"CAN bus initialization failed: {e}")
            raise
    
    def init_db_connection(self):
        """Initialize MySQL database connection"""
        try:
            self.db_connection = mysql.connector.connect(
                host="10.20.0.23",
                user="myuser1",
                password="root",
                database="khalil"
            )
            self.db_cursor = self.db_connection.cursor()
            print("MySQL database connection established")
            
            # Create table if not exists
            create_table_query = """
            CREATE TABLE IF NOT EXISTS protocol_data (
                event_id INT PRIMARY KEY,
                message INT NOT NULL,
                timestamp DATETIME
            )
            """
            self.db_cursor.execute(create_table_query)
            
            # Initialize missing window rows
            self.db_cursor.execute("SELECT event_id FROM protocol_data")
            existing_ids = {row[0] for row in self.db_cursor.fetchall()}
            
            required_ids = set(self.EVENT_IDS.values())
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
    
    def send_can_message(self, window, result, level, level_type, mode, safety):
        """
        Send CAN message using DBC definitions
        Args:
            window: Window identifier (DR, PS, DRS, PRS)
            result: Operation result code (OP, CL, etc.)
            level: Window level percentage (0-100)
            level_type: AUTO or MANUAL
            mode: WHONEN or FAHREN
            safety: ON or OFF
        """
        try:
            message = self.message_map[window]
            
            data = {
                f"{window}_LEVEL": level,
                f"{window}_RESULT": result,
                f"{window}_TYPE": level_type,
                f"{window}_MODE": mode,
                f"{window}_SAFETY": safety
            }
            
            encoded_msg = message.encode(data)
            
            msg = can.Message(
                arbitration_id=message.frame_id,
                data=encoded_msg,
                is_extended_id=False
            )
            
            self.bus.send(msg)
            print(f"Sent command: {window} | {result} | {level}% | {level_type} | {mode} | safety_{safety}")
            print(f"CAN ID: {hex(message.frame_id)}, Data: {encoded_msg}")
            
        except Exception as e:
            print(f"Error sending CAN message for {window}: {e}")
    
    def parse_response_frame(self, msg):
        """Parse response CAN message using DBC definitions"""
        try:
            for window, message in self.message_map.items():
                if msg.arbitration_id == message.frame_id:
                    decoded = self.db.decode_message(msg.arbitration_id, msg.data)
                    return {
                        window: {
                            "result": decoded[f"{window}_RESULT"],
                            "level": decoded[f"{window}_LEVEL"],
                            "level_type": decoded[f"{window}_TYPE"],
                            "mode": decoded[f"{window}_MODE"],
                            "safety": decoded[f"{window}_SAFETY"]
                        }
                    }
        except Exception as e:
            print(f"Error parsing response message: {e}")
        return None
    
    def write_response_to_file(self, status):
        """Write response status to window_response.txt"""
        try:
            with open("window_response.txt", 'a') as f:
                for window, data in status.items():
                    f.write(f"{window} | {data['result']} | {data['level']} | {data['level_type']} | {data['mode']} | safety_{data['safety']}\n")
            print("Response status written to window_response.txt")
        except Exception as e:
            print(f"Error writing to response file: {e}")
    
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
                event_id = self.EVENT_IDS[window]
                
                if self.last_processed_status[window] != level:
                    self.db_cursor.execute(update_query, (level, timestamp, event_id))
                    print(f"Database updated: {window} (ID:{event_id}) = {level}% at {timestamp}")
                    self.last_processed_status[window] = level
            
            self.db_connection.commit()
            
        except Error as e:
            print(f"Database update error: {e}")
            if not self.db_connection.is_connected():
                print("Database connection lost - will reconnect on next update")
    
    def monitor_responses(self):
        """Monitor CAN bus for response messages from slave"""
        print("CAN response monitor started...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg and msg.arbitration_id in [m.frame_id for m in self.message_map.values()]:
                    status = self.parse_response_frame(msg)
                    if status:
                        print("\nReceived Window Status Update:")
                        for window, data in status.items():
                            print(f"{window}: {data['result']} | {data['level']}% | {data['level_type']} | {data['mode']} | safety_{data['safety']}")
                        self.write_response_to_file(status)
                        self.update_database(status)
        except Exception as e:
            print(f"Response monitoring error: {e}")
    
    def start_response_monitor(self):
        """Start a thread to monitor response messages"""
        self.response_thread = threading.Thread(target=self.monitor_responses, daemon=True)
        self.response_thread.start()
    
    def monitor_file(self):
        """Monitor input file for new window commands"""
        print(f"Monitoring {self.filename} for new commands...")
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
                                    
                                    # Validate inputs against DBC definitions
                                    if window not in self.message_map:
                                        print(f"Invalid window: {window}")
                                        continue
                                        
                                    message_def = self.message_map[window]
                                    valid_results = [x.name for x in message_def.signals if x.name.endswith('_RESULT')][0].choices
                                    
                                    if result not in valid_results:
                                        print(f"Invalid result for {window}. Valid options: {list(valid_results.keys())}")
                                        continue
                                        
                                    if not 0 <= level <= 100:
                                        print(f"Invalid level (0-100%): {level}")
                                        continue
                                        
                                    self.send_can_message(window, result, level, level_type, mode, safety)
                                except (IndexError, ValueError) as e:
                                    print(f"Malformed command line: {line} - Error: {e}")
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """Cleanup resources on shutdown"""
        print("\nInitiating shutdown sequence...")
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
    try:
        master = CANWindowMaster("windows_analysis.txt")
        master.monitor_file()
    except Exception as e:
        print(f"Fatal error: {e}")