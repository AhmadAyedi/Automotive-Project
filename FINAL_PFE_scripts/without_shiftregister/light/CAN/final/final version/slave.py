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

# GPIO pins for LEDs with new configuration
LED_GROUPS = {
    "Low Beam": [1, 0],
    "High Beam": [1, 0, 17, 5],
    "Parking Left": [6, 13],
    "Parking Right": [12, 16],
    "Hazard Lights": [2, 3, 27, 22, 19, 26, 20, 21],
    "Left Turn": {
        "group1": [3, 2],
        "group2": [26, 19]
    },
    "Right Turn": {
        "group1": [22, 27],
        "group2": [21, 20]
    }
}

# Mode indicator LEDs
MODE_LEDS = {
    "Fahren": 7,
    "Stand": 23,
    "Parking": 18,
    "Wohnen": 24
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
        """Initialize all GPIO pins for LEDs."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Initialize all pins
        all_pins = []
        for light, pins in LED_GROUPS.items():
            if light in ["Left Turn", "Right Turn"]:
                all_pins.extend(pins["group1"])
                all_pins.extend(pins["group2"])
            else:
                all_pins.extend(pins)
        
        # Add mode indicator LEDs
        all_pins.extend(MODE_LEDS.values())
        
        # Remove duplicates and setup
        for pin in set(all_pins):
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        
        logging.info("GPIO initialized - All pins set to LOW")
    
    def update_mode_leds(self, mode_name):
        """Update the mode indicator LEDs based on current mode."""
        # Turn off all mode indicator LEDs first
        for pin in MODE_LEDS.values():
            GPIO.output(pin, GPIO.LOW)
        
        # Turn on the current mode LED
        if mode_name in MODE_LEDS:
            GPIO.output(MODE_LEDS[mode_name], GPIO.HIGH)
            self.current_mode = mode_name
            logging.info(f"Mode indicator set to {mode_name} (GPIO {MODE_LEDS[mode_name]})")
            
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
        for light in self.light_status:
            self.turn_off_light(light)
        
        # Turn off mode indicators
        for pin in MODE_LEDS.values():
            GPIO.output(pin, GPIO.LOW)
        
        if self.bus:
            self.bus.shutdown()
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        GPIO.cleanup()
        logging.info("Shutdown complete")

if __name__ == "__main__":
    slave = CANLightSlave()
    slave.receive_messages()