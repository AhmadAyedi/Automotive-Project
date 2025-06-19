import can
import RPi.GPIO as GPIO
import logging
import os
import time
from collections import defaultdict
import threading

# CAN IDs for each window type
WINDOW_IDS = {
    0x201: "DR",
    0x202: "PS",
    0x203: "DRS",
    0x204: "PRS"
}

# Response ID for slave responses
RESPONSE_ID = 0x300

# GPIO pins for each window's LEDs
WINDOW_LEDS = {
    "DR": [2, 3, 23, 17],    # DR window LEDs
    "PS": [27, 22, 0, 5],    # PS window LEDs
    "DRS": [6, 13, 19, 26],  # DRS window LEDs
    "PRS": [12, 16, 20, 21]  # PRS window LEDs
}

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
        # Track current level of each window (0-100)
        self.window_levels = {
            "DR": 0,
            "PS": 0,
            "DRS": 0,
            "PRS": 0
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
            self.window_levels[window] = new_level
    
    def create_response_frame(self):
        """Create CAN frame with current levels of all windows."""
        with self.lock:
            data = bytearray(4)
            data[0] = self.window_levels["DR"]
            data[1] = self.window_levels["PS"]
            data[2] = self.window_levels["DRS"]
            data[3] = self.window_levels["PRS"]
            return data
    
    def send_response(self):
        """Send response with current window levels back to master."""
        try:
            data = self.create_response_frame()
            msg = can.Message(
                arbitration_id=RESPONSE_ID,
                data=data,
                is_extended_id=False
            )
            self.bus.send(msg)
            print("\nSent Window Levels:")
            with self.lock:
                for window, level in self.window_levels.items():
                    print(f"{window}: {level}%")
            logging.info(f"Sent response CAN: {data.hex()}")
        except Exception as e:
            logging.error(f"CAN response send error: {e}")
    
    def handle_window_message(self, window, level):
        """Handle a window message in a separate thread."""
        self.update_window_leds(window, level)
        self.send_response()
    
    def receive_messages(self):
        print("Listening for CAN messages and controlling window LEDs...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg:
                    window = WINDOW_IDS.get(msg.arbitration_id)
                    level = msg.data[0] if msg.data else 0
                    
                    if window in WINDOW_LEDS and 0 <= level <= 100:
                        print(f"Received: {window} - Level: {level}%")
                        # Start a new thread to handle this window update
                        threading.Thread(
                            target=self.handle_window_message,
                            args=(window, level),
                            daemon=True
                        ).start()
                    else:
                        print(f"Ignoring unknown window or invalid level: {window} - {level}")
                
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