#!/usr/bin/env python3
import time
import can
import os
import re
import threading
from req import WiperSystem
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import json

class CANWiperMaster:
    def __init__(self):
        self.channel = 'can0'
        self.bustype = 'socketcan'
        self.bus = None
        self.wiper = WiperSystem("input.json", "wiper_output.txt")
        self.CAN_MSG_ID = 0x100
        self.RESPONSE_MSG_ID = 0x101
        self.last_modified = 0
        self.running = True
        self.db_connection = None
        self.db_cursor = None
        self.current_wiper_operation = 0  # To track WiperRequestOperation status

        self.init_can_bus()
        self.init_database()
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

    def init_database(self):
        try:
            self.db_connection = mysql.connector.connect(
                host="10.20.0.119",
                user="monuserr",
                password="khalil",
                database="khalil"
            )
            self.db_cursor = self.db_connection.cursor()
            print("Database connection established")

            # Check and initialize required rows if they don't exist
            self.initialize_database_rows()

        except Error as e:
            print(f"Database connection failed: {e}")
            raise

    def initialize_database_rows(self):
        """Ensure both event_id rows exist in the database"""
        # Check if row with event_id = 1 exists (WiperIgnition)
        self.db_cursor.execute("SELECT COUNT(*) FROM protocol_data WHERE event_id = 1")
        result = self.db_cursor.fetchone()
        if result[0] == 0:
            self.db_cursor.execute(
                "INSERT INTO protocol_data (event_id, message, timestamp) VALUES (1, 0, NOW())"
            )
            print("Inserted default row for WiperIgnition (event_id=1)")

        # Check if row with event_id = 2 exists (WiperRequestOperation)
        self.db_cursor.execute("SELECT COUNT(*) FROM protocol_data WHERE event_id = 2")
        result = self.db_cursor.fetchone()
        if result[0] == 0:
            self.db_cursor.execute(
                "INSERT INTO protocol_data (event_id, message, timestamp) VALUES (2, 0, NOW())"
            )
            print("Inserted default row for WiperRequestOperation (event_id=2)")

        self.db_connection.commit()

    def extract_signals(self, content):
        signals = {}
        matches = re.finditer(r'(\w+)\s*=\s*(\d+)', content)
        for match in matches:
            signals[match.group(1)] = int(match.group(2))
        return signals

    def create_can_frame(self, signals):
        data = bytearray(8)
        if 'wiperMode' in signals:
            data[0] = signals['wiperMode']
            self.current_wiper_operation = signals['wiperMode']  # Track current operation
        if 'wiperSpeed' in signals:
            data[1] = signals['wiperSpeed']
        if 'wiperCycleCount' in signals:
            data[2] = signals['wiperCycleCount']
        if 'WiperIntermittent' in signals:
            data[3] = signals['WiperIntermittent']
        if 'wipingCycle' in signals:
            data[4] = signals['wipingCycle'] & 0xFF
            data[5] = (signals['wipingCycle'] >> 8) & 0xFF
        data[6] = signals.get('Wiper_Function_Enabled', 1)
        return data

    def send_signals(self):
        try:
            self.wiper.process_operation()
            with open("wiper_output.txt", 'r') as f:
                content = f.read()
                print("\nGenerated Output:")
                print(content.strip())

                signals = self.extract_signals(content)
                print("\nSignals to transmit:", signals)

                can_data = self.create_can_frame(signals)
                self.send_can(can_data)

                # Also update the database with the current operation
                if 'wiperMode' in signals:
                    self.store_wiper_operation(signals['wiperMode'])

        except Exception as e:
            print(f"Error: {e}")

    def send_can(self, data):
        try:
            msg = can.Message(
                arbitration_id=self.CAN_MSG_ID,
                data=data,
                is_extended_id=False
            )
            self.bus.send(msg)
            print(f"Sent CAN: {data.hex()}")
        except Exception as e:
            print(f"CAN send error: {e}")

    def parse_response_frame(self, data):
        signals = {}
        signals['WiperStatus'] = data[0]
        signals['wiperCurrentSpeed'] = data[1]
        signals['wiperCurrentPosition'] = data[2]
        signals['currentWiperMode'] = data[3]
        signals['consumedPower'] = data[4]
        signals['isWiperBlocked'] = data[5]
        signals['blockageReason'] = data[6]
        signals['hwError'] = data[7]
        return signals

    def store_wiper_status(self, wiper_status):
        """Store WiperIgnition status (event_id=1)"""
        try:
            message = 1 if wiper_status == 1 else 0
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            event_id = 1

            query = """
            UPDATE protocol_data
            SET message = %s, timestamp = %s
            WHERE event_id = %s
            """
            values = (message, timestamp, event_id)

            self.db_cursor.execute(query, values)
            self.db_connection.commit()
            print(f"Updated WiperStatus={wiper_status} (message={message}) in database at {timestamp}")
        except Error as e:
            print(f"Error storing WiperStatus in database: {e}")

    def store_wiper_operation(self, operation):
        """Store WiperRequestOperation status (event_id=2)"""
        try:
            # operation can be 1 (touch), 2 (continuous), 3 (auto), or 4 (service)
            if operation not in [1, 2, 3, 4]:
                print(f"Invalid wiper operation value: {operation}")
                return

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            event_id = 2

            query = """
            UPDATE protocol_data
            SET message = %s, timestamp = %s
            WHERE event_id = %s
            """
            values = (operation, timestamp, event_id)

            self.db_cursor.execute(query, values)
            self.db_connection.commit()
            print(f"Updated WiperOperation={operation} in database at {timestamp}")
        except Error as e:
            print(f"Error storing WiperOperation in database: {e}")

    def monitor_responses(self):
        print("Listening for response CAN messages...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg and msg.arbitration_id == self.RESPONSE_MSG_ID:
                    signals = self.parse_response_frame(msg.data)
                    print("\nReceived Response Signals:")
                    for key, value in signals.items():
                        print(f"{key}: {value}")
                    
                    # Store both WiperStatus and current operation
                    self.store_wiper_status(signals['WiperStatus'])
                    self.store_wiper_operation(self.current_wiper_operation)
        except Exception as e:
            print(f"Response monitoring error: {e}")

    def start_response_monitor(self):
        self.response_thread = threading.Thread(target=self.monitor_responses, daemon=True)
        self.response_thread.start()

    def file_changed(self):
        try:
            mod_time = os.path.getmtime("input.json")
            if mod_time != self.last_modified:
                self.last_modified = mod_time
                return True
            return False
        except:
            return False

    def monitor(self):
        print("Monitoring input.json...")
        try:
            while self.running:
                if self.file_changed():
                    print("\n=== Input Changed ===")
                    self.send_signals()
                time.sleep(0.3)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        self.running = False
        if self.response_thread.is_alive():
            self.response_thread.join(timeout=0.5)
        if self.bus:
            self.bus.shutdown()
        if self.db_connection:
            if self.db_cursor:
                self.db_cursor.close()
            self.db_connection.close()
            print("Database connection closed")
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        print("Shutdown complete")

if __name__ == "__main__":
    master = CANWiperMaster()
    master.monitor()