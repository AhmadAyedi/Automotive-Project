import serial
import RPi.GPIO as GPIO
import time
import threading
import logging

# LIN Frame IDs for each light type
LIGHT_IDS = {
    0x10: "Low Beam",
    0x11: "High Beam",
    0x12: "Parking Left",
    0x13: "Parking Right",
    0x14: "Hazard Lights",
    0x15: "Right Turn",
    0x16: "Left Turn"
}

# Response IDs (same as light IDs for two-way communication)
RESPONSE_IDS = {
    "Low Beam": 0x10,
    "High Beam": 0x11,
    "Parking Left": 0x12,
    "Parking Right": 0x13,
    "Hazard Lights": 0x14,
    "Right Turn": 0x15,
    "Left Turn": 0x16
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

# LIN Constants
SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 19200
WAKEUP_PIN = 4
SYNC_BYTE = 0x55
BREAK_BYTE = 0x00

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('light_slave.log'),
        logging.StreamHandler()
    ]
)

class LINLightSlave:
    def __init__(self):
        self.running = True
        self.light_status = {
            "Low Beam": {"status": 0, "mode": "Stand"},
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
        
        self.setup_gpio()
        self.ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=0.1)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(WAKEUP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
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
    
    def calculate_pid(self, frame_id):
        if frame_id > 0x3F:
            raise ValueError("Frame ID must be 6 bits (0-63)")
        p0 = (frame_id ^ (frame_id >> 1) ^ (frame_id >> 2) ^ (frame_id >> 4)) & 0x01
        p1 = ~((frame_id >> 1) ^ (frame_id >> 3) ^ (frame_id >> 4) ^ (frame_id >> 5)) & 0x01
        return (frame_id & 0x3F) | (p0 << 6) | (p1 << 7)
    
    def calculate_checksum(self, pid, data):
        checksum = pid
        for byte in data:
            checksum += byte
            if checksum > 0xFF:
                checksum -= 0xFF
        return (0xFF - checksum) & 0xFF
    
    def parse_pid(self, pid_byte):
        frame_id = pid_byte & 0x3F
        p0 = (pid_byte >> 6) & 0x01
        p1 = (pid_byte >> 7) & 0x01
        calc_p0 = (frame_id ^ (frame_id >> 1) ^ (frame_id >> 2) ^ (frame_id >> 4)) & 0x01
        calc_p1 = ~((frame_id >> 1) ^ (frame_id >> 3) ^ (frame_id >> 4) ^ (frame_id >> 5)) & 0x01
        if p0 != calc_p0 or p1 != calc_p1:
            return None
        return frame_id
    
    def send_break(self):
        self.ser.baudrate = BAUD_RATE // 4
        self.ser.write(bytes([BREAK_BYTE]))
        self.ser.flush()
        time.sleep(13 * (1.0 / (BAUD_RATE // 4)))
        self.ser.baudrate = BAUD_RATE
    
    def send_lin_response(self, frame_id, data):
        """Send a complete LIN response frame (with break and sync)"""
        self.send_break()
        self.ser.write(bytes([SYNC_BYTE]))
        pid = self.calculate_pid(frame_id)
        self.ser.write(bytes([pid]))
        self.ser.write(data)
        checksum = self.calculate_checksum(pid, data)
        self.ser.write(bytes([checksum]))
        self.ser.flush()
        time.sleep(0.005)
    
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
            self.turn_off_light(light)
            self.light_status[light]["status"] = 0
            self.led_states[light] = False
            
        elif status_code == 0xFF:  # FAILED
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
    
    def create_status_response(self):
        """Create data frame with status of all lights (2 bytes per light - status and mode)"""
        light_order = [
            "Low Beam", "High Beam", "Parking Left", "Parking Right",
            "Hazard Lights", "Right Turn", "Left Turn"
        ]
        data = bytearray(14)  # 7 lights * 2 bytes each
        for i, light in enumerate(light_order):
            status = self.light_status[light]
            data[i*2] = 0x01 if status["status"] else 0x00  # Status byte
            # Mode byte
            if status["mode"] == "Fahren":
                data[i*2 + 1] = 0x01
            elif status["mode"] == "Stand":
                data[i*2 + 1] = 0x02
            elif status["mode"] == "Parking":
                data[i*2 + 1] = 0x03
            elif status["mode"] == "Wohnen":
                data[i*2 + 1] = 0x04
            else:
                data[i*2 + 1] = 0x02  # Default to Stand
        return data
    
    def process_light_command(self, frame_id, data):
        """Process a light control command from master"""
        if len(data) != 2:  # Expecting status and mode bytes
            logging.warning(f"Invalid data length for light command: {len(data)}")
            return
        
        status_code = data[0]
        mode_code = data[1]
        light = LIGHT_IDS.get(frame_id)
        
        if light:
            # Handle status and mode separately
            self.control_light_status(light, status_code)
            self.control_mode(mode_code)
            
            # Send status response after processing command
            time.sleep(0.01)
            self.send_status_response()
        else:
            logging.warning(f"Unknown frame ID received: {hex(frame_id)}")
    
    def send_status_response(self):
        """Send current status of all lights to master"""
        try:
            data = self.create_status_response()
            self.send_lin_response(0x18, data)  # 0x18 is our status response ID
            
            logging.info("Sent status response:")
            for i, light in enumerate([
                "Low Beam", "High Beam", "Parking Left", "Parking Right",
                "Hazard Lights", "Right Turn", "Left Turn"
            ]):
                status = "ON" if data[i*2] == 0x01 else "OFF"
                mode = MODE_CODES.get(data[i*2 + 1], "Unknown")
                logging.info(f"  {light}: {status} | {mode}")
                
        except Exception as e:
            logging.error(f"Error sending status response: {e}")
    
    def receive_messages(self):
        """Main loop to receive and process LIN messages"""
        buffer = bytes()
        logging.info("LIN Slave Node - Listening for frames...")
        
        try:
            while self.running:
                if self.ser.in_waiting:
                    byte = self.ser.read(1)
                    buffer += byte
                    
                    # Check for break character (start of LIN frame)
                    if byte == bytes([BREAK_BYTE]):
                        buffer = bytes([BREAK_BYTE])  # Start fresh frame
                        continue
                        
                    # Only proceed if we have break + sync
                    if len(buffer) >= 2 and buffer[0] == BREAK_BYTE and buffer[1] == SYNC_BYTE:
                        if len(buffer) >= 3:
                            pid_byte = buffer[2]
                            frame_id = self.parse_pid(pid_byte)
                            
                            if frame_id is not None:
                                # Check if this is a status request (ID 0x17)
                                if frame_id == 0x17:
                                    checksum = ord(self.ser.read(1)) if self.ser.in_waiting else None
                                    if checksum is not None:
                                        calc_checksum = self.calculate_checksum(pid_byte, bytes())
                                        if checksum == calc_checksum:
                                            logging.info("Received status request")
                                            self.send_status_response()
                                        else:
                                            logging.warning(f"Checksum mismatch in status request: received {hex(checksum)}, calculated {hex(calc_checksum)}")
                                    buffer = bytes()
                                
                                # Check if this is a light control command
                                elif frame_id in LIGHT_IDS:
                                    data = self.ser.read(2) if self.ser.in_waiting else None
                                    if data and len(data) == 2:
                                        checksum = ord(self.ser.read(1)) if self.ser.in_waiting else None
                                        if checksum is not None:
                                            calc_checksum = self.calculate_checksum(pid_byte, data)
                                            if checksum == calc_checksum:
                                                self.process_light_command(frame_id, data)
                                            else:
                                                logging.warning(f"Checksum mismatch in light command: received {hex(checksum)}, calculated {hex(calc_checksum)}")
                                        buffer = bytes()
                
                time.sleep(0.001)
                
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
        
        if self.ser:
            self.ser.close()
        GPIO.cleanup()
        logging.info("Shutdown complete")

if __name__ == "__main__":
    slave = LINLightSlave()
    slave.receive_messages()