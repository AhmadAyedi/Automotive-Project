import can
import RPi.GPIO as GPIO
import logging
import os
import time
from collections import defaultdict
import threading

# CAN IDs for each window type (same as master)
WINDOW_IDS = {
    "DR": 0x201,
    "PS": 0x202,
    "DRS": 0x203,
    "PRS": 0x204
}

# Response IDs (same as master's window IDs)
RESPONSE_IDS = {
    "DR": 0x201,
    "PS": 0x202,
    "DRS": 0x203,
    "PRS": 0x204
}

# GPIO pins for each window's LEDs
WINDOW_LEDS = {
    "DR": [2, 3, 23, 17],    # DR window LEDs
    "PS": [27, 22, 0, 5],    # PS window LEDs
    "DRS": [6, 13, 19, 26],  # DRS window LEDs
    "PRS": [12, 16, 20, 21]  # PRS window LEDs
}

# Result codes
RESULT_CODES = ["OP", "CL", "OPG", "CLG", "FOP", "OP_S", "CL_S", "OPG_S", "CLG_S", "FOP_S"]

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
        # Track current status of each window
        self.window_status = {
            "DR": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN"},
            "PS": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN"},
            "DRS": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN"},
            "PRS": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN"}
        }
        # Track current LED states (0-4 LEDs on)
        self.current_led_states = defaultdict(int)
        # Lock for thread-safe access to shared resources
        self.lock = threading.Lock()
        
        self.init_can_bus()
        self.setup_gpio()
    
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
        """Initialize GPIO pins for all window LEDs."""
        GPIO.setmode(GPIO.BCM)
        for leds in WINDOW_LEDS.values():
            for pin in leds:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)  # Initialize all LEDs to off
        logging.info("GPIO initialized")
    
    def get_required_leds(self, level):
        """Determine how many LEDs should be on based on the level."""
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
        """Update the LEDs for a window based on the new level."""
        required_leds = self.get_required_leds(new_level)
        current_leds = self.current_led_states[window]
        leds = WINDOW_LEDS[window]
        
        logging.info(f"Updating {window} from {current_leds} LEDs to {required_leds} LEDs (Level: {new_level}%)")
        
        # If we need to turn on more LEDs
        if required_leds > current_leds:
            for i in range(current_leds, required_leds):
                GPIO.output(leds[i], GPIO.HIGH)
                logging.info(f"Turned on {window} LED {i+1} (GPIO {leds[i]})")
                time.sleep(1)
        
        # If we need to turn off LEDs
        elif required_leds < current_leds:
            for i in range(current_leds-1, required_leds-1, -1):
                GPIO.output(leds[i], GPIO.LOW)
                logging.info(f"Turned off {window} LED {i+1} (GPIO {leds[i]})")
                time.sleep(1)
        
        # Update current state
        with self.lock:
            self.current_led_states[window] = required_leds
            self.window_status[window]["level"] = new_level
    
    def send_window_response(self, window):
        """Send response for a specific window back to master."""
        try:
            with self.lock:
                status = self.window_status[window]
                result_index = RESULT_CODES.index(status["result"])
                level = status["level"]
                level_type = LEVEL_TYPES.index(status["level_type"])
                mode = MODES.index(status["mode"])
                
                msg_data = [result_index, level, level_type, mode]
                
                msg = can.Message(
                    arbitration_id=RESPONSE_IDS[window],
                    data=msg_data,
                    is_extended_id=False
                )
                
                self.bus.send(msg)
                print(f"Sent Response: {window} | {status['result']} | {status['level']}% | {status['level_type']} | {status['mode']} (ID: {hex(RESPONSE_IDS[window])}, Data: {msg_data})")
                logging.info(f"Sent response for {window}: {msg_data}")
        except Exception as e:
            logging.error(f"Error sending {window} response: {e}")
    
    def handle_window_message(self, window, result, level, level_type, mode):
        """Handle a window message in a separate thread."""
        with self.lock:
            self.window_status[window]["result"] = result
            self.window_status[window]["level_type"] = level_type
            self.window_status[window]["mode"] = mode
        
        self.update_window_leds(window, level)
        
        # Send response for this window
        self.send_window_response(window)
    
    def receive_messages(self):
        print("Listening for CAN messages and controlling window LEDs...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg:
                    window = next((name for name, can_id in WINDOW_IDS.items() if can_id == msg.arbitration_id), None)
                    if window and len(msg.data) >= 2:
                        result_index = msg.data[0]
                        level = msg.data[1]
                        # Default to AUTO/WHONEN if not provided in message
                        level_type = LEVEL_TYPES[msg.data[2]] if len(msg.data) > 2 else "AUTO"
                        mode = MODES[msg.data[3]] if len(msg.data) > 3 else "WHONEN"
                        
                        if (window in WINDOW_LEDS and 0 <= level <= 100 and 
                            0 <= result_index < len(RESULT_CODES) and
                            level_type in LEVEL_TYPES and mode in MODES):
                            result = RESULT_CODES[result_index]
                            print(f"Received: {window} | {result} | {level}% | {level_type} | {mode}")
                            # Start a new thread to handle this window update
                            threading.Thread(
                                target=self.handle_window_message,
                                args=(window, result, level, level_type, mode),
                                daemon=True
                            ).start()
                        else:
                            print(f"Ignoring invalid message: {window} - {result_index} - {level} - {level_type} - {mode}")
                
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
        GPIO.cleanup()
        logging.info("Shutdown complete")

if __name__ == "__main__":
    slave = CANWindowSlave()
    slave.receive_messages()