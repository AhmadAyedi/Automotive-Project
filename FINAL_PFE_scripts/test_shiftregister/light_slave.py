import can
import RPi.GPIO as GPIO
import logging
import os
import time
import threading

# Light ID definitions (matches master)
LIGHT_IDS = {
    0x101: "Low Beam",
    0x102: "High Beam",
    0x103: "Parking Left",
    0x104: "Parking Right",
    0x105: "Hazard Lights",
    0x106: "Right Turn",
    0x107: "Left Turn"
}

# Response IDs (same as light IDs for two-way communication)
RESPONSE_IDS = {
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
    0x01: "ON",
    0x00: "OFF",
    0xFF: "FAILED",
    0xFE: "INVALID"
}

# Mode codes
MODE_CODES = {
    0x01: "Fahren",
    0x02: "Stand",
    0x03: "Parking",
    0x04: "Wohnen"
}

# LED Groups using shift register LED positions (1-based indexing converted to 0-based)
LED_GROUPS = {
    "Low Beam": [32, 23],  # LEDs 33, 24 -> indices 32, 23
    "High Beam": [32, 23, 33, 0],  # LEDs 33, 24, 34, 1 -> indices 32, 23, 33, 0
    "Parking Left": [34, 35],  # LEDs 35, 36 -> indices 34, 35
    "Parking Right": [39, 16],  # LEDs 40, 17 -> indices 39, 16
    "Hazard Lights": [3, 31, 38, 37, 21, 20, 19, 18],  # LEDs 4, 32, 39, 38, 22, 21, 20, 19 -> indices 3, 31, 38, 37, 21, 20, 19, 18
    "Left Turn": {
        "group1": [3, 31],  # LEDs 4, 32 -> indices 3, 31
        "group2": [38, 37]  # LEDs 39, 38 -> indices 38, 37
    },
    "Right Turn": {
        "group1": [21, 20],  # LEDs 22, 21 -> indices 21, 20
        "group2": [19, 18]  # LEDs 20, 19 -> indices 19, 18
    }
}

# Mode indicator LEDs (1-based indexing converted to 0-based)
MODE_LEDS = {
    "Fahren": 4,   # LED 5 -> index 4
    "Stand": 36,   # LED 37 -> index 36
    "Parking": 17, # LED 18 -> index 17
    "Wohnen": 22   # LED 23 -> index 22
}

# GPIO Pins for 74HC595
SHIFT_REGISTER_PINS = {
    'Latch': 13,
    'Clock': 15,
    'Serial_Input': 11,
    'Clear': 7
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
        self.bustype = 'socketcan'
        self.bus = None
        self.running = True
        self.light_status = {
            "Low Beam": {"status": 0, "mode": "Stand", "should_be_on": False},
            "High Beam": {"status": 0, "mode": "Stand"},
            "Parking Left": {"status": 0, "mode": "Stand"},
            "Parking Right": {"status": 0, "mode": "Stand"},
            "Hazard Lights": {"status": 0, "mode": "Stand"},
            "Right Turn": {"status": 0, "mode": "Stand"},
            "Left Turn": {"status": 0, "mode": "Stand"}
        }
        self.led_states = {light: False for light in LIGHT_IDS.values()}
        self.hazard_thread = None
        self.left_turn_thread = None
        self.right_turn_thread = None
        self.hazard_running = False
        self.left_turn_running = False
        self.right_turn_running = False
        self.current_mode = "Stand"
        
        # Shift register state (40 LEDs, all OFF initially)
        self.leds_status = [0] * 40
        
        self.init_can_bus()
        self.setup_shift_register()
    
    def init_can_bus(self):
        try:
            os.system(f'sudo /sbin/ip link set {self.channel} up type can bitrate 500000')
            time.sleep(0.1)
            self.bus = can.interface.Bus(channel=self.channel, bustype=self.bustype)
            logging.info("CAN initialized")
        except Exception as e:
            logging.error(f"CAN init failed: {e}")
            raise
    
    def setup_shift_register(self):
        """Initialize GPIO pins for 74HC595 shift register control."""
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)
        
        # Setup shift register control pins
        for pin_name, pin_number in SHIFT_REGISTER_PINS.items():
            GPIO.setup(pin_number, GPIO.OUT)
        
        # Initialize shift register
        self.clear_shift_register()
        self.update_shift_register()
        
        logging.info("Shift register initialized - All LEDs OFF")
    
    def clear_shift_register(self):
        """Clear all shift register outputs."""
        GPIO.output(SHIFT_REGISTER_PINS['Clear'], 0)
        GPIO.output(SHIFT_REGISTER_PINS['Clear'], 1)
        self.leds_status = [0] * 40
    
    def shift_out_data(self, data):
        """Shift out data to the 74HC595 registers."""
        # Shift data out bit by bit (MSB first for each register)
        for state in data:
            GPIO.output(SHIFT_REGISTER_PINS['Serial_Input'], state)
            GPIO.output(SHIFT_REGISTER_PINS['Clock'], 0)
            GPIO.output(SHIFT_REGISTER_PINS['Clock'], 1)
        
        # Latch the data to outputs
        GPIO.output(SHIFT_REGISTER_PINS['Latch'], 0)
        GPIO.output(SHIFT_REGISTER_PINS['Latch'], 1)
    
    def update_shift_register(self):
        """Update the shift register with current LED states."""
        self.shift_out_data(self.leds_status)
    
    def set_led(self, index, state):
        """Set a specific LED state and update shift register."""
        if 0 <= index < 40:
            self.leds_status[index] = 1 if state else 0
            self.update_shift_register()
    
    def set_multiple_leds(self, indices, state):
        """Set multiple LEDs to the same state and update shift register once."""
        for index in indices:
            if 0 <= index < 40:
                self.leds_status[index] = 1 if state else 0
        self.update_shift_register()
    
    def update_mode_leds(self, mode_name):
        """Update the mode indicator LEDs based on current mode."""
        # Turn off all mode indicator LEDs first
        for mode, led_index in MODE_LEDS.items():
            self.set_led(led_index, False)
        
        # Turn on the current mode LED
        if mode_name in MODE_LEDS:
            self.set_led(MODE_LEDS[mode_name], True)
            self.current_mode = mode_name
            logging.info(f"Mode indicator set to {mode_name} (LED {MODE_LEDS[mode_name] + 1})")
            
            # Special handling for Low Beam based on mode change
            if self.light_status["Low Beam"]["should_be_on"]:
                if mode_name in ["Fahren", "Wohnen"]:
                    self.turn_on_light("Low Beam")
                    self.light_status["Low Beam"]["status"] = 1
                else:
                    self.turn_off_light("Low Beam")
                    self.light_status["Low Beam"]["status"] = 0
    
    def control_light_status(self, light, status_code):
        """Control the light based only on status code (ON/OFF/FAILED/INVALID)."""
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
        
        if status_code == 0x01:  # ON
            if light == "Low Beam":
                # Mark that Low Beam should be on (if in correct mode)
                self.light_status["Low Beam"]["should_be_on"] = True
                if self.current_mode in ["Fahren", "Wohnen"]:
                    self.turn_on_light(light)
                    self.light_status[light]["status"] = 1
                    self.led_states[light] = True
                else:
                    self.turn_off_light(light)
                    self.light_status[light]["status"] = 0
                    self.led_states[light] = False
            else:
                # Normal behavior for other lights
                if light == "Hazard Lights":
                    self.start_hazard_lights()
                elif light == "Left Turn":
                    self.start_left_turn()
                elif light == "Right Turn":
                    self.start_right_turn()
                else:
                    self.turn_on_light(light)
                
                self.light_status[light]["status"] = 1
                self.led_states[light] = True
            
        elif status_code == 0x00:  # OFF
            if light == "Low Beam":
                self.light_status["Low Beam"]["should_be_on"] = False
            self.turn_off_light(light)
            self.light_status[light]["status"] = 0
            self.led_states[light] = False
            
        elif status_code == 0xFF:  # FAILED
            if light == "Low Beam":
                self.light_status["Low Beam"]["should_be_on"] = False
            self.turn_off_light(light)
            self.light_status[light]["status"] = 0
            self.led_states[light] = False
            
        elif status_code == 0xFE:  # INVALID - keep previous state
            return
        
        status_name = STATUS_CODES.get(status_code, f"Unknown: {hex(status_code)}")
        logging.info(f"Controlled {light}: {status_name}")
    
    def control_mode(self, mode_code):
        """Control the mode indicator LEDs based only on mode code."""
        if mode_code not in [0x01, 0x02, 0x03, 0x04]:
            logging.warning(f"Invalid mode code received: {hex(mode_code)}")
            return
        
        mode_name = MODE_CODES.get(mode_code, "Stand")
        self.update_mode_leds(mode_name)
        
        # Update mode in all light statuses
        for light in self.light_status:
            self.light_status[light]["mode"] = mode_name
        
        logging.info(f"Updated mode to: {mode_name}")
    
    def turn_on_light(self, light):
        """Turn on a simple light (non-blinking, non-flowing)."""
        if light in ["Hazard Lights", "Left Turn", "Right Turn"]:
            return
        
        led_indices = LED_GROUPS.get(light, [])
        self.set_multiple_leds(led_indices, True)
    
    def turn_off_light(self, light):
        """Turn off a light and stop any effects."""
        if light == "Hazard Lights":
            led_indices = LED_GROUPS["Hazard Lights"]
        elif light == "Left Turn":
            led_indices = LED_GROUPS["Left Turn"]["group1"] + LED_GROUPS["Left Turn"]["group2"]
        elif light == "Right Turn":
            led_indices = LED_GROUPS["Right Turn"]["group1"] + LED_GROUPS["Right Turn"]["group2"]
        else:
            led_indices = LED_GROUPS.get(light, [])
        
        self.set_multiple_leds(led_indices, False)
    
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
        led_indices = LED_GROUPS["Hazard Lights"]
        while self.hazard_running:
            self.set_multiple_leds(led_indices, True)
            time.sleep(0.5)
            self.set_multiple_leds(led_indices, False)
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
            self.set_multiple_leds([group1[0], group2[0]], True)
            time.sleep(0.3)
            
            # Second LED in each group (while keeping first on)
            self.set_multiple_leds([group1[1], group2[1]], True)
            time.sleep(0.3)
            
            # Turn off first LED in each group
            self.set_multiple_leds([group1[0], group2[0]], False)
            time.sleep(0.3)
            
            # Turn off second LED in each group
            self.set_multiple_leds([group1[1], group2[1]], False)
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
            self.set_multiple_leds([group1[0], group2[0]], True)
            time.sleep(0.3)
            
            # Second LED in each group (while keeping first on)
            self.set_multiple_leds([group1[1], group2[1]], True)
            time.sleep(0.3)
            
            # Turn off first LED in each group
            self.set_multiple_leds([group1[0], group2[0]], False)
            time.sleep(0.3)
            
            # Turn off second LED in each group
            self.set_multiple_leds([group1[1], group2[1]], False)
            time.sleep(0.3)
    
    def send_light_response(self, light):
        """Send response for a specific light"""
        try:
            status_data = self.light_status[light]
            msg_data = [
                0x01 if status_data["status"] else 0x00,  # Status
                [k for k, v in MODE_CODES.items() if v == status_data["mode"]][0]  # Mode code
            ]
            
            msg = can.Message(
                arbitration_id=RESPONSE_IDS[light],
                data=msg_data,
                is_extended_id=False
            )
            
            self.bus.send(msg)
            logging.info(f"Sent response for {light}: Status={msg_data[0]}, Mode={msg_data[1]}")
            print(f"Sent Response: {light} | {'ON' if msg_data[0] else 'OFF'} | {status_data['mode']}")
        except Exception as e:
            logging.error(f"Error sending {light} response: {e}")
    
    def receive_messages(self):
        print("Listening for CAN messages and controlling lights...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg:
                    light = LIGHT_IDS.get(msg.arbitration_id)
                    if light and len(msg.data) >= 2:
                        status_code = msg.data[0]
                        mode_code = msg.data[1]
                        
                        print(f"Received: {light} | {STATUS_CODES.get(status_code, 'UNKNOWN')} | {MODE_CODES.get(mode_code, 'UNKNOWN')}")
                        
                        # Handle status and mode separately
                        self.control_light_status(light, status_code)
                        self.control_mode(mode_code)
                        self.send_light_response(light)
                
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
        self.clear_shift_register()
        self.update_shift_register()
        
        if self.bus:
            self.bus.shutdown()
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        GPIO.cleanup()
        logging.info("Shutdown complete")

if __name__ == "__main__":
    slave = CANLightSlave()
    slave.receive_messages()