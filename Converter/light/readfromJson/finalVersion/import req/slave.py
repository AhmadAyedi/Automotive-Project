import can
import RPi.GPIO as GPIO
import logging
import os
import time
import threading

# Light ID definitions
LIGHT_IDS = {
    "Low Beam": 0x101,
    "High Beam": 0x102,
    "Parking Left": 0x103,
    "Parking Right": 0x104,
    "Hazard Lights": 0x105,
    "Right Turn": 0x106,
    "Left Turn": 0x107
}

# Status codes
STATUS_CODES = {
    "activated": 0x01,
    "desactivated": 0x00,
    "FAILED": 0xFF,
    "INVALID": 0xFE
}

# Reverse mappings
LIGHT_NAMES = {
    0x101: "Low Beam",
    0x102: "High Beam",
    0x103: "Parking Left",
    0x104: "Parking Right",
    0x105: "Hazard Lights",
    0x106: "Right Turn",
    0x107: "Left Turn"
}

STATUS_NAMES = {
    0x01: "activated",
    0x00: "desactivated",
    0xFF: "FAILED",
    0xFE: "INVALID"
}

# GPIO pins for LEDs with new configuration
LED_GROUPS = {
    "Low Beam": [3, 22],
    "High Beam": [3, 22, 2, 27],
    "Parking Left": [19, 26],
    "Parking Right": [20, 21],
    "Hazard Lights": [18, 24, 7],
    "Left Turn": {
        "group1": [23, 17],
        "group2": [6, 13]
    },
    "Right Turn": {
        "group1": [0, 5],
        "group2": [12, 16]
    }
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('light_slave.log'),
        logging.StreamHandler()
    ]
)

class CANLightSlave:
    def __init__(self):
        self.channel = 'can0'
        self.bus = None
        self.running = True
        self.RESPONSE_ID = 0x200
        # Track light statuses (store 1 for ON, 0 for OFF for database)
        self.light_statuses = {
            "Low Beam": 0,
            "High Beam": 0,
            "Parking Left": 0,
            "Parking Right": 0,
            "Hazard Lights": 0,
            "Right Turn": 0,
            "Left Turn": 0
        }
        # Track current LED states (ON/OFF)
        self.led_states = {
            "Low Beam": False,
            "High Beam": False,
            "Parking Left": False,
            "Parking Right": False,
            "Hazard Lights": False,
            "Right Turn": False,
            "Left Turn": False
        }
        # Thread control for blinking and flowing effects
        self.hazard_thread = None
        self.left_turn_thread = None
        self.right_turn_thread = None
        self.hazard_running = False
        self.left_turn_running = False
        self.right_turn_running = False
        
        self.init_can_bus()
        self.setup_gpio()
    
    def init_can_bus(self):
        try:
            os.system(f'sudo /sbin/ip link set {self.channel} down 2>/dev/null')
            time.sleep(0.1)
            os.system(f'sudo /sbin/ip link set {self.channel} up type can bitrate 500000')
            time.sleep(0.1)
            self.bus = can.interface.Bus(interface='socketcan', channel=self.channel)
            logging.info("CAN initialized")
        except Exception as e:
            logging.error(f"CAN init failed: {e}")
            raise
    
    def setup_gpio(self):
        """Initialize all GPIO pins for LEDs."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Initialize all pins
        all_pins = []
        for light, pins in LED_GROUPS.items():
            if light in ["Left Turn", "Right Turn"]:
                all_pins.extend(pins["group1"])
                all_pins.extend(pins["group2"])
            elif light == "Hazard Lights":
                all_pins.extend(pins)
            else:
                all_pins.extend(pins)
        
        # Remove duplicates and setup
        for pin in set(all_pins):
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        
        logging.info("GPIO initialized - All pins set to LOW")
    
    def control_led(self, light, status_code):
        """Control the LED based on the light type and status code."""
        if status_code not in [0x01, 0x00, 0xFF, 0xFE]:
            logging.warning(f"Invalid status code received for {light}: {hex(status_code)}")
            return
        
        # Stop any running effects first
        if light == "Hazard Lights":
            self.stop_hazard_lights()
        elif light == "Left Turn":
            self.stop_left_turn()
        elif light == "Right Turn":
            self.stop_right_turn()
        
        if status_code == 0x01:  # activated
            if light == "Hazard Lights":
                self.start_hazard_lights()
            elif light == "Left Turn":
                self.start_left_turn()
            elif light == "Right Turn":
                self.start_right_turn()
            else:
                self.turn_on_light(light)
            
            self.light_statuses[light] = 1
            self.led_states[light] = True
            
        elif status_code == 0x00:  # desactivated
            self.turn_off_light(light)
            self.light_statuses[light] = 0
            self.led_states[light] = False
            
        elif status_code == 0xFF:  # FAILED
            self.turn_off_light(light)
            self.light_statuses[light] = 0
            self.led_states[light] = False
            
        elif status_code == 0xFE:  # INVALID - keep previous state
            pass
        
        status_name = STATUS_NAMES.get(status_code, f"Unknown code: {hex(status_code)}")
        logging.info(f"Controlled LED: {light} = {status_name} ({hex(status_code)})")
    
    def turn_on_light(self, light):
        """Turn on a simple light (non-blinking, non-flowing)."""
        if light in ["Hazard Lights", "Left Turn", "Right Turn"]:
            return
        
        pins = LED_GROUPS.get(light, [])
        for pin in pins:
            GPIO.output(pin, GPIO.HIGH)
    
    def turn_off_light(self, light):
        """Turn off a light and stop any effects."""
        if light == "Hazard Lights":
            pins = LED_GROUPS["Hazard Lights"]
        elif light == "Left Turn":
            pins = LED_GROUPS["Left Turn"]["group1"] + LED_GROUPS["Left Turn"]["group2"]
        elif light == "Right Turn":
            pins = LED_GROUPS["Right Turn"]["group1"] + LED_GROUPS["Right Turn"]["group2"]
        else:
            pins = LED_GROUPS.get(light, [])
        
        for pin in pins:
            GPIO.output(pin, GPIO.LOW)
    
    def start_hazard_lights(self):
        """Start the hazard lights blinking effect."""
        self.hazard_running = True
        self.hazard_thread = threading.Thread(target=self.hazard_effect, daemon=True)
        self.hazard_thread.start()
    
    def stop_hazard_lights(self):
        """Stop the hazard lights blinking effect."""
        self.hazard_running = False
        if self.hazard_thread and self.hazard_thread.is_alive():
            self.hazard_thread.join(timeout=0.5)
        self.turn_off_light("Hazard Lights")
    
    def hazard_effect(self):
        """Blinking effect for hazard lights."""
        pins = LED_GROUPS["Hazard Lights"]
        while self.hazard_running:
            for pin in pins:
                GPIO.output(pin, GPIO.HIGH)
            time.sleep(0.5)
            for pin in pins:
                GPIO.output(pin, GPIO.LOW)
            time.sleep(0.5)
    
    def start_left_turn(self):
        """Start the left turn flowing effect."""
        self.left_turn_running = True
        self.left_turn_thread = threading.Thread(target=self.left_turn_effect, daemon=True)
        self.left_turn_thread.start()
    
    def stop_left_turn(self):
        """Stop the left turn flowing effect."""
        self.left_turn_running = False
        if self.left_turn_thread and self.left_turn_thread.is_alive():
            self.left_turn_thread.join(timeout=0.5)
        self.turn_off_light("Left Turn")
    
    def left_turn_effect(self):
        """Flowing effect for left turn signals."""
        group1 = LED_GROUPS["Left Turn"]["group1"]
        group2 = LED_GROUPS["Left Turn"]["group2"]
        
        while self.left_turn_running:
            # First LED in each group
            GPIO.output(group1[0], GPIO.HIGH)
            GPIO.output(group2[0], GPIO.HIGH)
            time.sleep(0.3)
            
            # Second LED in each group (while keeping first on)
            GPIO.output(group1[1], GPIO.HIGH)
            GPIO.output(group2[1], GPIO.HIGH)
            time.sleep(0.3)
            
            # Turn off first LED in each group
            GPIO.output(group1[0], GPIO.LOW)
            GPIO.output(group2[0], GPIO.LOW)
            time.sleep(0.3)
            
            # Turn off second LED in each group
            GPIO.output(group1[1], GPIO.LOW)
            GPIO.output(group2[1], GPIO.LOW)
            time.sleep(0.3)
    
    def start_right_turn(self):
        """Start the right turn flowing effect."""
        self.right_turn_running = True
        self.right_turn_thread = threading.Thread(target=self.right_turn_effect, daemon=True)
        self.right_turn_thread.start()
    
    def stop_right_turn(self):
        """Stop the right turn flowing effect."""
        self.right_turn_running = False
        if self.right_turn_thread and self.right_turn_thread.is_alive():
            self.right_turn_thread.join(timeout=0.5)
        self.turn_off_light("Right Turn")
    
    def right_turn_effect(self):
        """Flowing effect for right turn signals."""
        group1 = LED_GROUPS["Right Turn"]["group1"]
        group2 = LED_GROUPS["Right Turn"]["group2"]
        
        while self.right_turn_running:
            # First LED in each group
            GPIO.output(group1[0], GPIO.HIGH)
            GPIO.output(group2[0], GPIO.HIGH)
            time.sleep(0.3)
            
            # Second LED in each group (while keeping first on)
            GPIO.output(group1[1], GPIO.HIGH)
            GPIO.output(group2[1], GPIO.HIGH)
            time.sleep(0.3)
            
            # Turn off first LED in each group
            GPIO.output(group1[0], GPIO.LOW)
            GPIO.output(group2[0], GPIO.LOW)
            time.sleep(0.3)
            
            # Turn off second LED in each group
            GPIO.output(group1[1], GPIO.LOW)
            GPIO.output(group2[1], GPIO.LOW)
            time.sleep(0.3)
    
    def create_response_frame(self):
        """Create CAN frame with status of all lights."""
        light_order = [
            "Low Beam", "High Beam", "Parking Left", "Parking Right",
            "Hazard Lights", "Right Turn", "Left Turn"
        ]
        data = bytearray(7)
        for i, light in enumerate(light_order):
            data[i] = self.light_statuses[light]  # 1 for ON, 0 for OFF
        return data
    
    def send_response(self):
        """Send response signals back to master."""
        try:
            data = self.create_response_frame()
            msg = can.Message(
                arbitration_id=self.RESPONSE_ID,
                data=data,
                is_extended_id=False
            )
            self.bus.send(msg)
            
            print("\nSent Response Signals (Raw):")
            light_order = [
                0x101,  # Low Beam
                0x102,  # High Beam
                0x103,  # Parking Left
                0x104,  # Parking Right
                0x105,  # Hazard Lights
                0x106,  # Right Turn
                0x107   # Left Turn
            ]
            for i, light_id in enumerate(light_order):
                print(f"ID: {hex(light_id)}, Status: {hex(data[i])}")
            
            logging.info(f"Sent response CAN: {data.hex()}")
        except Exception as e:
            logging.error(f"CAN response send error: {e}")
    
    def receive_messages(self):
        print("Listening for CAN messages and controlling LEDs...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg:
                    light = LIGHT_NAMES.get(msg.arbitration_id, f"Unknown ID: {hex(msg.arbitration_id)}")
                    status_code = msg.data[0] if msg.data else 0xFF
                    status_name = STATUS_NAMES.get(status_code, f"Unknown status: {hex(status_code)}")
                    print(f"Received: {light} - {status_name} (Code: {hex(status_code)})")
                    
                    if light in self.light_statuses:
                        self.control_led(light, status_code)
                        self.send_response()
                    else:
                        print(f"No LED control for: {light}")
                
        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt")
        finally:
            self.shutdown()
    
    def shutdown(self):
        logging.info("Shutting down...")
        self.running = False
        
        # Stop all effects
        self.stop_hazard_lights()
        self.stop_left_turn()
        self.stop_right_turn()
        
        # Turn off all LEDs
        for light in self.light_statuses:
            self.turn_off_light(light)
        
        if self.bus:
            self.bus.shutdown()
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        GPIO.cleanup()
        logging.info("Shutdown complete")

if __name__ == "__main__":
    slave = CANLightSlave()
    slave.receive_messages()