#!/usr/bin/env python3
"""
Professional CAN Window Slave Controller
Uses DBC file and cantools for CAN communication
Controls window LEDs based on received commands
"""

import can
import RPi.GPIO as GPIO
import logging
import os
import time
from collections import defaultdict
import threading
import cantools

class CANWindowSlave:
    def __init__(self):
        self.channel = 'can0'
        self.bustype = 'socketcan'
        self.bus = None
        self.running = True
        
        # GPIO Pins for 74HC595 (BCM numbering)
        self.Latch = 27    # BOARD 13
        self.Clock = 22    # BOARD 15
        self.Serial_Input = 17  # BOARD 11
        self.Clear = 4     # BOARD 7
        
        # Status indicator LEDs
        self.RED_LED = 18
        self.GREEN_LED = 24
        self.YELLOW_LED = 23
        
        # Safety LED in shift register (LED 2 = index 1)
        self.SAFETY_LED_INDEX = 1
        
        # LED indices for each window
        self.WINDOW_LEDS = {
            "DR": [11, 12, 13, 14],     # Driver Window - LED 12-15
            "PS": [27, 26, 25, 24],     # Passenger Window - LED 28-25
            "DRS": [2, 8, 9, 10],      # Rear Driver Window - LED 3,9-11
            "PRS": [15, 30, 29, 28]    # Rear Passenger Window - LED 16,31-29
        }
        
        # Load DBC file and create message map
        self.db = cantools.database.load_file('window_system.dbc')
        self.message_map = {
            "DR": self.db.get_message_by_name("DR_CTRL"),
            "PS": self.db.get_message_by_name("PS_CTRL"),
            "DRS": self.db.get_message_by_name("DRS_CTRL"),
            "PRS": self.db.get_message_by_name("PRS_CTRL")
        }
        
        # Initialize window status
        self.window_status = {
            "DR": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN", "safety": "OFF"},
            "PS": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN", "safety": "OFF"},
            "DRS": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN", "safety": "OFF"},
            "PRS": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN", "safety": "OFF"}
        }
        
        self.current_led_states = defaultdict(int)
        self.LEDs_status = [0] * 40  # 40-bit shift register status
        self.lock = threading.Lock()
        self.led_update_lock = threading.Lock()
        
        self.init_can_bus()
        self.setup_gpio()
        self.clear_register()
        self.shift_out(self.LEDs_status)
        
        # Start with green LED on
        GPIO.output(self.GREEN_LED, GPIO.HIGH)
    
    def init_can_bus(self):
        """Initialize CAN bus interface"""
        try:
            os.system(f'sudo /sbin/ip link set {self.channel} up type can bitrate 500000')
            time.sleep(0.1)
            self.bus = can.interface.Bus(channel=self.channel, bustype=self.bustype)
            logging.info("CAN bus initialized successfully")
        except Exception as e:
            logging.error(f"CAN bus initialization failed: {e}")
            raise
    
    def setup_gpio(self):
        """Initialize GPIO pins"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup shift register pins
        GPIO.setup(self.Clock, GPIO.OUT)
        GPIO.setup(self.Latch, GPIO.OUT)
        GPIO.setup(self.Clear, GPIO.OUT)
        GPIO.setup(self.Serial_Input, GPIO.OUT)
        
        # Setup status indicator LEDs
        GPIO.setup(self.RED_LED, GPIO.OUT)
        GPIO.setup(self.GREEN_LED, GPIO.OUT)
        GPIO.setup(self.YELLOW_LED, GPIO.OUT)
        
        # Initialize states
        GPIO.output(self.RED_LED, GPIO.LOW)
        GPIO.output(self.GREEN_LED, GPIO.HIGH)
        GPIO.output(self.YELLOW_LED, GPIO.LOW)
        
        logging.info("GPIO initialized successfully")
    
    def clear_register(self):
        """Clear all LEDs in the shift register"""
        GPIO.output(self.Clear, 0)
        GPIO.output(self.Clear, 1)
        logging.info("Shift register cleared")
    
    def shift_out(self, data):
        """Shift out data to the 74HC595 shift register"""
        with self.led_update_lock:
            for state in data:
                GPIO.output(self.Serial_Input, state)
                GPIO.output(self.Clock, 0)
                GPIO.output(self.Clock, 1)
            GPIO.output(self.Latch, 0)
            GPIO.output(self.Latch, 1)
    
    def update_safety_led(self, safety_status):
        """Update the safety LED in shift register"""
        with self.lock:
            if safety_status == "ON":
                self.LEDs_status[self.SAFETY_LED_INDEX] = 1
                logging.info("Safety LED turned ON")
            else:
                self.LEDs_status[self.SAFETY_LED_INDEX] = 0
                logging.info("Safety LED turned OFF")
        
        self.shift_out(self.LEDs_status)
    
    def update_status_leds(self, result, safety):
        """Update the status LEDs based on window state"""
        GPIO.output(self.RED_LED, GPIO.LOW)
        GPIO.output(self.GREEN_LED, GPIO.LOW)
        GPIO.output(self.YELLOW_LED, GPIO.LOW)
        
        if result == "FAILED":
            GPIO.output(self.YELLOW_LED, GPIO.HIGH)
            logging.info("System fault - Yellow LED activated")
        elif safety == "ON":
            GPIO.output(self.RED_LED, GPIO.HIGH)
            logging.info("Safety active - Red LED activated")
        else:
            GPIO.output(self.GREEN_LED, GPIO.HIGH)
            logging.info("Normal operation - Green LED active")
    
    def get_required_leds(self, level):
        """Determine how many LEDs should be on based on level percentage"""
        if level == 0:
            return 0
        elif 1 <= level <= 24:
            return 0
        elif 25 <= level <= 49:
            return 1
        elif 50 <= level <= 74:
            return 2
        elif 75 <= level <= 99:
            return 3
        elif level == 100:
            return 4
    
    def update_window_leds(self, window, new_level):
        """Update window LEDs with animation effect"""
        required_leds = self.get_required_leds(new_level)
        current_leds = self.current_led_states[window]
        leds = self.WINDOW_LEDS[window]
        
        logging.info(f"Updating {window} from {current_leds} to {required_leds} LEDs (Level: {new_level}%)")
        
        # Animate LED changes
        if required_leds > current_leds:
            # Turn on LEDs sequentially
            for i in range(current_leds, required_leds):
                with self.lock:
                    self.LEDs_status[leds[i]] = 1
                self.shift_out(self.LEDs_status)
                logging.info(f"Turned on {window} LED {i+1}")
                time.sleep(0.3)
        elif required_leds < current_leds:
            # Turn off LEDs sequentially
            for i in range(current_leds-1, required_leds-1, -1):
                with self.lock:
                    self.LEDs_status[leds[i]] = 0
                self.shift_out(self.LEDs_status)
                logging.info(f"Turned off {window} LED {i+1}")
                time.sleep(0.3)
        
        with self.lock:
            self.current_led_states[window] = required_leds
            self.window_status[window]["level"] = new_level
    
    def send_window_response(self, window):
        """Send current window status back to master"""
        try:
            with self.lock:
                status = self.window_status[window]
                message = self.message_map[window]
                
                data = {
                    f"{window}_LEVEL": status["level"],
                    f"{window}_RESULT": status["result"],
                    f"{window}_TYPE": status["level_type"],
                    f"{window}_MODE": status["mode"],
                    f"{window}_SAFETY": status["safety"]
                }
                
                encoded_msg = message.encode(data)
                
                msg = can.Message(
                    arbitration_id=message.frame_id,
                    data=encoded_msg,
                    is_extended_id=False
                )
                
                self.bus.send(msg)
                logging.info(f"Sent {window} status response: {data}")
                print(f"Sent Response: {window} | {status['result']} | {status['level']}% | {status['level_type']} | {status['mode']} | safety_{status['safety']}")
                
        except Exception as e:
            logging.error(f"Failed to send {window} response: {e}")
    
    def handle_window_message(self, window, data):
        """Process received window command"""
        result = data[f"{window}_RESULT"]
        level = data[f"{window}_LEVEL"]
        level_type = data[f"{window}_TYPE"]
        mode = data[f"{window}_MODE"]
        safety = data[f"{window}_SAFETY"]
        
        logging.info(f"Processing {window} command: {result} {level}% {level_type} {mode} safety_{safety}")
        
        # Update status indicators
        self.update_status_leds(result, safety)
        self.update_safety_led(safety)
        
        # Update window status
        with self.lock:
            self.window_status[window]["result"] = result
            self.window_status[window]["level_type"] = level_type
            self.window_status[window]["mode"] = mode
            self.window_status[window]["safety"] = safety
        
        # Handle window movement unless failed
        if result != "FAILED":
            self.update_window_leds(window, level)
        
        # Always send response
        self.send_window_response(window)
    
    def receive_messages(self):
        """Main CAN message processing loop"""
        logging.info("Starting CAN message receiver")
        print("Listening for window control commands...")
        
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg:
                    try:
                        for window, message in self.message_map.items():
                            if msg.arbitration_id == message.frame_id:
                                data = self.db.decode_message(msg.arbitration_id, msg.data)
                                print(f"Received: {window} | {data[f'{window}_RESULT']} | {data[f'{window}_LEVEL']}% | {data[f'{window}_TYPE']} | {data[f'{window}_MODE']} | safety_{data[f'{window}_SAFETY']}")
                                threading.Thread(
                                    target=self.handle_window_message,
                                    args=(window, data),
                                    daemon=True
                                ).start()
                                break
                    except Exception as e:
                        logging.error(f"Message processing error: {e}")
                
        except KeyboardInterrupt:
            logging.info("Received shutdown signal")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Cleanup resources on shutdown"""
        logging.info("Initiating shutdown sequence")
        self.running = False
        
        # Turn off all LEDs in shift register
        self.LEDs_status = [0] * 40
        self.shift_out(self.LEDs_status)
        
        # Turn off status LEDs
        GPIO.output(self.RED_LED, GPIO.LOW)
        GPIO.output(self.GREEN_LED, GPIO.LOW)
        GPIO.output(self.YELLOW_LED, GPIO.LOW)
        
        if self.bus:
            self.bus.shutdown()
        
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        GPIO.cleanup()
        
        logging.info("Shutdown complete")
        print("Window controller stopped")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('window_slave.log'),
            logging.StreamHandler()
        ]
    )
    
    try:
        slave = CANWindowSlave()
        slave.receive_messages()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        raise