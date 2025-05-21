#!/usr/bin/env python3
from lin_protocol import LINMaster
import time
from pymongo import MongoClient
import logging
import board
import adafruit_dht
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('wiper_master.log'),
        logging.StreamHandler()
    ]
)

class WiperController:
    def __init__(self):
        self.lin_master = LINMaster()
        self.mongo_client = MongoClient('mongodb://10.20.0.27:27017/')
        self.db = self.mongo_client.LIN_wiper77
        self.commands_collection = self.db.commands
        self.sensor_collection = self.db.sensors
        self.dht = adafruit_dht.DHT11(board.D17)  # GPIO17
        self.last_sensor_read = 0
        self.sensor_read_interval = 2.0  # Read sensor every 2 seconds
        self.is_automatic_mode = False  # Track manual/automatic mode
        self.automatic_frame_data = self._command_to_frame_data('both', 'normal', 5)  # Frame for automatic mode
        self.stop_frame_data = bytes([0, 0, 0])  # Frame to stop wipers
        
    def _command_to_frame_data(self, wiper_type, speed, cycles):
        """Convert command to LIN frame data bytes"""
        # Wiper type: 1=front, 2=back, 3=both (parallel), 0=stop
        wiper_byte = 1 if wiper_type == 'front' else \
                    2 if wiper_type == 'back' else \
                    3 if wiper_type == 'both' else 0
        
        # Speed: 1=normal, 2=fast, 0 for stop
        speed_byte = 1 if speed == 'normal' else \
                    2 if speed == 'fast' else 0
        
        # Cycles: 1-5, 0 for stop
        cycles_byte = min(max(cycles, 1), 5) if wiper_type != 'stop' else 0
        
        return bytes([wiper_byte, speed_byte, cycles_byte])
            
    def read_and_store_sensor_data(self):
        """Read DHT11 sensor, store data in MongoDB, and manage wiper mode"""
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
                    logging.info(f"Stored sensor data: Temp={temp}C, Humidity={humidity}%")
                    
                    # Check temperature and toggle mode
                    if temp >= 26 and not self.is_automatic_mode:
                        self.is_automatic_mode = True
                        logging.info("Switching to automatic mode (temperature >= 26C)")
                        # Clear pending commands to prevent interference
                        self.commands_collection.update_many(
                            {"status": "pending"},
                            {"$set": {"status": "ignored"}}
                        )
                    elif temp < 26 and self.is_automatic_mode:
                        self.is_automatic_mode = False
                        logging.info("Switching to manual mode (temperature < 26C)")
                        # Send stop command to slave
                        try:
                            self.lin_master.send_frame(0x20, self.stop_frame_data)
                            logging.info(f"Sent stop frame to slave: {self.stop_frame_data}")
                        except Exception as e:
                            logging.error(f"Error sending stop frame: {e}")
                else:
                    logging.warning("Failed to read valid sensor data")
                    
            except RuntimeError as e:
                logging.error(f"Error reading sensor: {e}")
                
            self.last_sensor_read = current_time
            
    def process_pending_commands(self):
        """Process pending wiper commands from MongoDB in manual mode"""
        if self.is_automatic_mode:
            # In automatic mode, send continuous wiper commands
            try:
                self.lin_master.send_frame(0x20, self.automatic_frame_data)
                logging.info(f"Automatic mode: Sent LIN frame for both wipers: {self.automatic_frame_data}")
            except Exception as e:
                logging.error(f"Error sending automatic frame: {e}")
        else:
            # In manual mode, process user commands
            try:
                pending_commands = self.commands_collection.find({"status": "pending"})
                
                for command in pending_commands:
                    frame_data = self._command_to_frame_data(
                        command['wiperType'],
                        command['speed'],
                        command['cycles']
                    )
                    
                    try:
                        self.lin_master.send_frame(0x20, frame_data)
                        logging.info(f"Manual mode: Sent LIN frame: {frame_data}")
                        
                        self.commands_collection.update_one(
                            {"_id": command["_id"]},
                            {"$set": {"status": "completed"}}
                        )
                        
                    except Exception as e:
                        logging.error(f"Error sending frame: {e}")
                        
            except Exception as e:
                logging.error(f"Error processing commands: {e}")
            
    def run(self):
        """Main loop for processing commands and sensor data"""
        try:
            while True:
                self.read_and_store_sensor_data()
                self.process_pending_commands()
                time.sleep(0.5)  # Short delay to prevent excessive CPU usage
                
        except KeyboardInterrupt:
            logging.info("Shutting down...")
        finally:
            self.lin_master.close()
            self.mongo_client.close()
            try:
                self.dht.exit()
            except:
                pass

if __name__ == "__main__":
    controller = WiperController()
    controller.run()
