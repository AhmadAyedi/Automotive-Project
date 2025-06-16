#!/usr/bin/env python3
"""
Professional CAN Light Master Controller with DBC support - Fixed Version
"""

import can
import time
import os
import threading
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import cantools

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
        self.last_processed_status = {}
        self.last_processed_mode = {}
        
        # Database event IDs for each light
        self.EVENT_IDS = {
            "LOW_BEAM": 11,
            "HIGH_BEAM": 12,
            "PARKING_LEFT": 18,
            "PARKING_RIGHT": 17,
            "HAZARD_LIGHTS": 13,
            "RIGHT_TURN": 15,
            "LEFT_TURN": 14
        }

        # Load DBC file and create message map
        self.db = cantools.database.load_file('light_system.dbc')
        self.message_map = {
            "LOW_BEAM": self.db.get_message_by_name("LOW_BEAM_CTRL"),
            "HIGH_BEAM": self.db.get_message_by_name("HIGH_BEAM_CTRL"),
            "PARKING_LEFT": self.db.get_message_by_name("PARKING_LEFT_CTRL"),
            "PARKING_RIGHT": self.db.get_message_by_name("PARKING_RIGHT_CTRL"),
            "HAZARD_LIGHTS": self.db.get_message_by_name("HAZARD_LIGHTS_CTRL"),
            "RIGHT_TURN": self.db.get_message_by_name("RIGHT_TURN_CTRL"),
            "LEFT_TURN": self.db.get_message_by_name("LEFT_TURN_CTRL")
        }
        
        # Initialize last processed status
        for light in self.message_map:
            self.last_processed_status[light] = None
            self.last_processed_mode[light] = None
        
        self.init_can_bus()
        self.init_db_connection()
        self.start_response_monitor()
    
    def init_can_bus(self):
        """Initialize CAN bus interface"""
        try:
            if not os.path.exists(f'/sys/class/net/{self.channel}'):
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
            
            # Initialize missing light rows
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
                print(f"Initialized {len(missing_ids)} missing light rows in protocol_data")
            
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            raise
    
    def send_can_message(self, light, status, mode):
        """
        Send CAN message using DBC definitions
        Args:
            light: Light identifier (e.g. "LOW_BEAM")
            status: Light status ("ON", "OFF", etc.)
            mode: Operation mode ("FAHREN", "STAND", etc.)
        """
        try:
            message = self.message_map[light]
            
            # Convert status and mode to raw values if they're named signals
            status_value = status if isinstance(status, int) else None
            mode_value = mode if isinstance(mode, int) else None
            
            data = {
                f"{light}_STATUS": status_value if status_value is not None else status,
                f"{light}_MODE": mode_value if mode_value is not None else mode
            }
            
            encoded_msg = message.encode(data)
            
            msg = can.Message(
                arbitration_id=message.frame_id,
                data=encoded_msg,
                is_extended_id=False
            )
            
            self.bus.send(msg)
            print(f"Sent command: {light} | {status} | {mode}")
            print(f"CAN ID: {hex(message.frame_id)}, Data: {encoded_msg.hex()}")
            
        except Exception as e:
            print(f"Error sending CAN message for {light}: {e}")
    
    def parse_response_frame(self, msg):
        """Parse response CAN message using DBC definitions"""
        try:
            for light, message in self.message_map.items():
                if msg.arbitration_id == message.frame_id:
                    decoded = self.db.decode_message(msg.arbitration_id, msg.data)
                    
                    # Convert named signal values to strings
                    status = decoded[f"{light}_STATUS"]
                    mode = decoded[f"{light}_MODE"]
                    
                    if hasattr(status, 'name'):
                        status = status.name
                    if hasattr(mode, 'name'):
                        mode = mode.name
                    
                    return {
                        light: {
                            "status": status,
                            "mode": mode
                        }
                    }
        except Exception as e:
            print(f"Error parsing response message: {e}")
        return None
    
    def write_response_to_file(self, status):
        """Write response status to light_response.txt"""
        try:
            with open("light_response.txt", 'a') as f:
                for light, data in status.items():
                    f.write(f"{light} | {data['status']} | {data['mode']}\n")
            print("Response status written to light_response.txt")
        except Exception as e:
            print(f"Error writing to response file: {e}")
    
    def update_database(self, status):
        """Update the database with light status"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            if not self.db_connection.is_connected():
                self.init_db_connection()
            
            update_query = """
            UPDATE protocol_data
            SET message = %s, timestamp = %s
            WHERE event_id = %s
            """
            
            for light, data in status.items():
                status_value = 1 if data['status'] == "ON" else 0
                event_id = self.EVENT_IDS[light]
                
                if self.last_processed_status[light] != status_value:
                    self.db_cursor.execute(update_query, (status_value, timestamp, event_id))
                    print(f"Database updated: {light} (ID:{event_id}) = {status_value} at {timestamp}")
                    self.last_processed_status[light] = status_value
            
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
                        print("\nReceived Light Status Update:")
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
        """Monitor input file for new light commands"""
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
                            if line.strip() and line.startswith("Light:"):
                                try:
                                    parts = [p.strip() for p in line.split('|')]
                                    if len(parts) < 3:
                                        print(f"Skipping incomplete line: {line}")
                                        continue
                                        
                                    light_name = parts[0].split(':')[1].strip().upper().replace(' ', '_')
                                    status = parts[1].split(':')[1].strip().upper()
                                    mode = parts[2].split(':')[1].strip().upper()
                                    
                                    # Validate inputs
                                    if light_name not in self.message_map:
                                        print(f"Invalid light: {light_name}")
                                        continue
                                        
                                    if status not in ["ON", "OFF", "FAILED", "INVALID"]:
                                        print(f"Invalid status (ON/OFF/FAILED/INVALID): {status}")
                                        continue
                                        
                                    if mode not in ["FAHREN", "STAND", "PARKING", "WOHNEN"]:
                                        print(f"Invalid mode (FAHREN/STAND/PARKING/WOHNEN): {mode}")
                                        continue
                                        
                                    if (self.last_processed_status[light_name] != status or 
                                        self.last_processed_mode[light_name] != mode):
                                        self.send_can_message(light_name, status, mode)
                                        self.last_processed_status[light_name] = status
                                        self.last_processed_mode[light_name] = mode
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
        master = CANLightMaster("Lights_analysis.txt")
        master.monitor_file()
    except Exception as e:
        print(f"Fatal error: {e}")