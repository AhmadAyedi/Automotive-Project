# -*- coding: utf-8 -*-
import can
import RPi.GPIO as GPIO
import logging
import os
import time
from collections import defaultdict
import threading

# CAN IDs for each window type (matches master)
WINDOW_IDS = {
    0x201: "DR",
    0x202: "PS",
    0x203: "DRS",
    0x204: "PRS"
}

# Response IDs (same as window IDs for two-way communication)
RESPONSE_IDS = {
    "DR": 0x201,
    "PS": 0x202,
    "DRS": 0x203,
    "PRS": 0x204
}

# GPIO Pins for 74HC595 (converted to BCM numbering)
Latch = 27  # BOARD 13 = BCM 27
Clock = 22  # BOARD 15 = BCM 22
Serial_Input = 17  # BOARD 11 = BCM 17
Clear = 4   # BOARD 7 = BCM 4

# LED indices for each window in the 40-LED shift register array
WINDOW_LEDS = {
    "DR": [11, 12, 13, 14],           # Driver Window - LED 12–15
    "PS": [27, 26, 25, 24],           # Passenger Window - LED 28–25
    "DRS": [2, 8, 9, 10],            # Rear Driver Window - LED 3, 9–11
    "PRS": [15, 30, 29, 28]          # Rear Passenger Window - LED 16, 31, 30, 29
}

# Status indicator LEDs (using BCM numbering - avoiding system pins)
RED_LED = 18
GREEN_LED = 24  # Changed from 7 to avoid SPI conflict
YELLOW_LED = 23

# Safety LED in shift register (LED 2 = index 1)
SAFETY_LED_INDEX = 1

# Result codes
RESULT_CODES = ["OP", "CL", "OPG", "CLG", "FOP", "OP_D", "CL_D", "OPG_D", "CLG_D", "FOP_D", 
                "OP_AD", "CL_AD", "OPG_AD", "CLG_AD", "FOP_AD", "OP_A", "CL_A", "OPG_A", "CLG_A", "FOP_A", "FAILED"]

# Level types and modes
LEVEL_TYPES = ["AUTO", "MANUAL"]
MODES = ["WHONEN", "FAHREN"]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('window_slave.log'),
        logging.StreamHandler()
    ]
)

class CANWindowSlave:
    def __init__(self):
        self.channel = 'can0'
        self.bustype = 'socketcan'
        self.bus = None
        self.running = True
        self.window_status = {
            "DR": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN", "safety": "OFF"},
            "PS": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN", "safety": "OFF"},
            "DRS": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN", "safety": "OFF"},
            "PRS": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN", "safety": "OFF"}
        }
        self.current_led_states = defaultdict(int)
        self.LEDs_status = [0] * 40  # 40-bit shift register status
        self.lock = threading.Lock()
        
        self.init_can_bus()
        self.setup_gpio()
        self.clear_register()
        self.shift_out(self.LEDs_status)
    
    def init_can_bus(self):
        try:
            os.system(f'sudo /sbin/ip link set {self.channel} up type can bitrate 500000')
            time.sleep(0.1)
            self.bus = can.interface.Bus(channel=self.channel, bustype=self.bustype)
            logging.info("CAN initialized")
        except Exception as e:
            logging.error(f"CAN init failed: {e}")
            raise
    
    def setup_gpio(self):
        # Setup all GPIO pins using BCM numbering consistently
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup shift register pins
        GPIO.setup(Clock, GPIO.OUT)
        GPIO.setup(Latch, GPIO.OUT)
        GPIO.setup(Clear, GPIO.OUT)
        GPIO.setup(Serial_Input, GPIO.OUT)
        
        # Setup status indicator LEDs
        GPIO.setup(RED_LED, GPIO.OUT)
        GPIO.setup(GREEN_LED, GPIO.OUT)
        GPIO.setup(YELLOW_LED, GPIO.OUT)
        GPIO.output(RED_LED, GPIO.LOW)
        GPIO.output(GREEN_LED, GPIO.HIGH)  # Start with green LED on by default
        GPIO.output(YELLOW_LED, GPIO.LOW)  # Yellow LED off by default
        
        logging.info("GPIO initialized")
    
    def clear_register(self):
        """Clear all LEDs in the shift register"""
        GPIO.output(Clear, 0)
        GPIO.output(Clear, 1)
    
    def shift_out(self, data):
        """Shift out data to the 74HC595 shift register"""
        for state in data:
            GPIO.output(Serial_Input, state)
            GPIO.output(Clock, 0)
            GPIO.output(Clock, 1)
        GPIO.output(Latch, 0)
        GPIO.output(Latch, 1)
    
    def update_safety_led(self, safety_status):
        """Update the safety LED in shift register based on safety status"""
        if safety_status == "ON":
            self.LEDs_status[SAFETY_LED_INDEX] = 1
            logging.info(f"Safety ON - turning on LED 2 (index {SAFETY_LED_INDEX})")
        else:
            self.LEDs_status[SAFETY_LED_INDEX] = 0
            logging.info(f"Safety OFF - turning off LED 2 (index {SAFETY_LED_INDEX})")
        
        self.shift_out(self.LEDs_status)
    
    def update_status_leds(self, result, safety):
        """Update the status LEDs based on the result code and safety status"""
        # First turn off all status LEDs
        GPIO.output(RED_LED, GPIO.LOW)
        GPIO.output(GREEN_LED, GPIO.LOW)
        GPIO.output(YELLOW_LED, GPIO.LOW)
        
        if result == "FAILED":
            GPIO.output(YELLOW_LED, GPIO.HIGH)
            logging.info(f"FAILED status detected, turning on yellow LED")
        elif safety == "ON":
            GPIO.output(RED_LED, GPIO.HIGH)
            logging.info(f"Safety ON detected, turning on red LED")
        else:
            GPIO.output(GREEN_LED, GPIO.HIGH)
            logging.info(f"Normal operation, turning on green LED")
    
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
        """Update window LEDs using shift register with animation"""
        required_leds = self.get_required_leds(new_level)
        current_leds = self.current_led_states[window]
        leds = WINDOW_LEDS[window]
        
        logging.info(f"Updating {window} from {current_leds} LEDs to {required_leds} LEDs (Level: {new_level}%)")
        
        # Animate LED changes
        if required_leds > current_leds:
            # Turn on LEDs one by one
            for i in range(current_leds, required_leds):
                self.LEDs_status[leds[i]] = 1
                self.shift_out(self.LEDs_status)
                logging.info(f"Turned on {window} LED {i+1} (Index {leds[i]})")
                time.sleep(1)
        elif required_leds < current_leds:
            # Turn off LEDs one by one
            for i in range(current_leds-1, required_leds-1, -1):
                self.LEDs_status[leds[i]] = 0
                self.shift_out(self.LEDs_status)
                logging.info(f"Turned off {window} LED {i+1} (Index {leds[i]})")
                time.sleep(1)
        
        with self.lock:
            self.current_led_states[window] = required_leds
            self.window_status[window]["level"] = new_level
    
    def send_window_response(self, window):
        try:
            with self.lock:
                status = self.window_status[window]
                msg_data = [
                    RESULT_CODES.index(status["result"]),
                    status["level"],
                    LEVEL_TYPES.index(status["level_type"]),
                    MODES.index(status["mode"]),
                    1 if status["safety"] == "ON" else 0
                ]
                
                msg = can.Message(
                    arbitration_id=RESPONSE_IDS[window],
                    data=msg_data,
                    is_extended_id=False
                )
                
                self.bus.send(msg)
                print(f"Sent Response: {window} | {status['result']} | {status['level']}% | {status['level_type']} | {status['mode']} | safety_{status['safety']} (ID: {hex(RESPONSE_IDS[window])}, Data: {msg_data})")
                logging.info(f"Sent response for {window}: {msg_data}")
        except Exception as e:
            logging.error(f"Error sending {window} response: {e}")
    
    def handle_window_message(self, window, result, level, level_type, mode, safety):
        # First update the status LEDs based on the result and safety
        self.update_status_leds(result, safety)
        
        # Update safety LED in shift register
        self.update_safety_led(safety)
        
        # Skip LED updates if result is FAILED
        if result == "FAILED":
            logging.info(f"Received FAILED status for {window}, skipping LED update")
            with self.lock:
                # Still update the status fields (except level) for the response
                self.window_status[window]["result"] = result
                self.window_status[window]["level_type"] = level_type
                self.window_status[window]["mode"] = mode
                self.window_status[window]["safety"] = safety
        else:
            # Normal processing for non-FAILED results
            with self.lock:
                self.window_status[window]["result"] = result
                self.window_status[window]["level_type"] = level_type
                self.window_status[window]["mode"] = mode
                self.window_status[window]["safety"] = safety
            
            self.update_window_leds(window, level)
        
        # Always send response even for FAILED status
        self.send_window_response(window)
    
    def receive_messages(self):
        print("Listening for CAN messages and controlling window LEDs via shift register...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg:
                    window = WINDOW_IDS.get(msg.arbitration_id)
                    if window and len(msg.data) >= 5:
                        try:
                            result_index = msg.data[0]
                            level = msg.data[1]
                            level_type = LEVEL_TYPES[msg.data[2]] if len(msg.data) > 2 else "AUTO"
                            mode = MODES[msg.data[3]] if len(msg.data) > 3 else "WHONEN"
                            safety = "ON" if msg.data[4] == 1 else "OFF"
                            
                            if (0 <= level <= 100 and 
                                0 <= result_index < len(RESULT_CODES)):
                                result = RESULT_CODES[result_index]
                                print(f"Received: {window} | {result} | {level}% | {level_type} | {mode} | safety_{safety}")
                                threading.Thread(
                                    target=self.handle_window_message,
                                    args=(window, result, level, level_type, mode, safety),
                                    daemon=True
                                ).start()
                        except (IndexError, ValueError) as e:
                            print(f"Error processing message: {e}")
                
        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt")
        finally:
            self.shutdown()
    
    def shutdown(self):
        logging.info("Shutting down...")
        self.running = False
        if self.bus:
            self.bus.shutdown()
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        
        # Turn off all LEDs in shift register
        self.LEDs_status = [0] * 40
        self.shift_out(self.LEDs_status)
        
        # Turn off status LEDs
        GPIO.output(RED_LED, GPIO.LOW)
        GPIO.output(GREEN_LED, GPIO.LOW)
        GPIO.output(YELLOW_LED, GPIO.LOW)
        
        GPIO.cleanup()
        logging.info("Shutdown complete")

if __name__ == "__main__":
    slave = CANWindowSlave()
    slave.receive_messages()