#!/usr/bin/env python3
from lin_protocol import LINMaster
import can
import time
from pymongo import MongoClient
import logging
import board
import adafruit_dht
from datetime import datetime
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('wiper_master_unified.log'),
        logging.StreamHandler()
    ]
)

class WiperController:
    def __init__(self):
        # Initialize both communication interfaces
        self.lin_master = LINMaster()
        try:
            self.can_bus = can.interface.Bus(channel='can0', bustype='socketcan')
        except Exception as e:
            logging.error(f"CAN initialization failed: {e}")
            raise
        
        # MongoDB setup - single database
        self.mongo_client = MongoClient('mongodb://192.168.1.14:27017/')
        self.db = self.mongo_client.CAN_LIN_wiper777
        self.commands_collection = self.db.commands
        self.sensor_collection = self.db.sensors
        self.dht = adafruit_dht.DHT11(board.D17)
        
        # State variables
        self.last_sensor_read = 0
        self.sensor_read_interval = 2.0
        self.is_automatic_mode = False
        self.automatic_frame_data = self._command_to_frame_data('both', 'normal', 0)
        self.stop_frame_data = bytes([0, 0, 0])
        self.last_mode_switch = 0
        self.mode_switch_delay = 1.0
        
    def _command_to_frame_data(self, wiper_type, speed, cycles):
        """Convert command parameters to frame data bytes"""
        wiper_byte = 1 if wiper_type == 'front' else \
                    2 if wiper_type == 'back' else \
                    3 if wiper_type == 'both' else 0
        
        speed_byte = 1 if speed == 'normal' else \
                    2 if speed == 'fast' else 0
        
        cycles_byte = min(max(cycles, 0), 5) if wiper_type != 'stop' else 0
        
        return bytes([wiper_byte, speed_byte, cycles_byte])
    
    def _send_message(self, data, protocol):
        """Send message using the specified protocol"""
        if protocol.upper() == 'LIN':
            try:
                self.lin_master.send_frame(0x20, data)
                return True
            except Exception as e:
                logging.error(f"LIN send error: {e}")
                return False
        elif protocol.upper() == 'CAN':
            try:
                msg = can.Message(
                    arbitration_id=0x123,
                    data=data,
                    is_extended_id=False
                )
                self.can_bus.send(msg)
                return True
            except can.CanError as e:
                logging.error(f"CAN send error: {e}")
                return False
        else:
            logging.error(f"Unknown protocol: {protocol}")
            return False
    
    def _send_stop_command(self, protocol='LIN'):
        """Send stop command with guaranteed delivery"""
        if self._send_message(self.stop_frame_data, protocol):
            logging.info(f"Sent STOP command via {protocol}")
            return True
        return False
            
    def read_and_store_sensor_data(self):
        current_time = time.time()
        if current_time - self.last_sensor_read >= self.sensor_read_interval:
            try:
                temp = self.dht.temperature
                humidity = self.dht.humidity
                if temp is not None and humidity is not None:
                    sensor_data = {
                        'temperature': temp,
                        'humidity': humidity,
                        'timestamp': datetime.utcnow()
                    }
                    self.sensor_collection.insert_one(sensor_data)
                    logging.info(f"Sensor data: Temp={temp}C, Humidity={humidity}%")
                    
                    previous_mode = self.is_automatic_mode
                    new_mode = temp >= 27
                    
                    if current_time - self.last_mode_switch >= self.mode_switch_delay:
                        if not previous_mode and new_mode:
                            logging.info("ACTIVATING automatic mode (temp >=27C)")
                            self.is_automatic_mode = True
                            self.last_mode_switch = current_time
                            self.commands_collection.update_many(
                                {"status": "pending"},
                                {"$set": {"status": "ignored"}}
                            )
                        elif previous_mode and not new_mode:
                            logging.info("DEACTIVATING automatic mode (temp <27C)")
                            self.is_automatic_mode = False
                            self.last_mode_switch = current_time
                            if not self._send_stop_command('LIN'):  # Default to LIN for auto mode
                                logging.error("Stop command not confirmed!")
                            self.commands_collection.update_many(
                                {"status": "pending"},
                                {"$set": {"status": "ignored"}}
                            )
                
            except RuntimeError as e:
                logging.error(f"Sensor read error: {e}")
                
            self.last_sensor_read = current_time
            
    def process_pending_commands(self):
        if self.is_automatic_mode:
            if time.time() - self.last_mode_switch < 0.5:
                if self._send_message(self.automatic_frame_data, 'LIN'):  # Auto mode uses LIN
                    logging.info("Sent automatic mode activation frame via LIN")
        else:
            try:
                # Get only commands with status 'pending'
                pending_commands = self.commands_collection.find({"status": "pending"})
                
                for command in pending_commands:
                    # Verify the command has a protocol field
                    if 'protocol' not in command:
                        logging.error("Command missing protocol field, skipping")
                        continue
                        
                    frame_data = self._command_to_frame_data(
                        command['wiperType'],
                        command['speed'],
                        command['cycles']
                    )
                    
                    if self._send_message(frame_data, command['protocol']):
                        logging.info(f"Executed {command['protocol']} command: {command['wiperType']} {command['speed']}")
                        self.commands_collection.update_one(
                            {"_id": command["_id"]},
                            {"$set": {"status": "completed"}}
                        )
                    else:
                        logging.error(f"Failed to execute {command['protocol']} command")
            except Exception as e:
                logging.error(f"Command processing error: {e}")
            
    def run(self):
        try:
            logging.info("Starting unified wiper controller (supports both CAN and LIN)")
            while True:
                self.read_and_store_sensor_data()
                self.process_pending_commands()
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logging.info("Shutdown initiated")
        finally:
            logging.info("Cleaning up resources")
            # Send stop commands on both protocols
            self._send_stop_command('LIN')
            self._send_stop_command('CAN')
            self.lin_master.close()
            self.can_bus.shutdown()
            self.mongo_client.close()
            try:
                self.dht.exit()
            except:
                pass

if __name__ == "__main__":
    controller = WiperController()
    controller.run()