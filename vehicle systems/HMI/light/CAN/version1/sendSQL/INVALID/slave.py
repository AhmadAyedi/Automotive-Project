import can
import RPi.GPIO as GPIO
import logging
import os
import time

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

# GPIO pins for LEDs
LED_PINS = {
    "Low Beam": 23,
    "High Beam": 24,
    "Parking Right": 26,
    "Parking Left": 16,
    "Hazard Lights": 20,
    "Right Turn": 21,
    "Left Turn": 6
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
        """Initialize GPIO pins for LEDs."""
        GPIO.setmode(GPIO.BCM)
        for pin in LED_PINS.values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)  # Initialize LEDs to off
        logging.info("GPIO initialized")
    
    def control_led(self, light, status_code):
        """Control the LED based on the light type and status code."""
        pin = LED_PINS.get(light)
        if pin is not None:
            if status_code == 0x01:  # activated
                GPIO.output(pin, GPIO.HIGH)
                self.light_statuses[light] = 1  # ON for database
            elif status_code == 0x00:  # desactivated
                GPIO.output(pin, GPIO.LOW)
                self.light_statuses[light] = 0  # OFF for database
            else:  # 0xFF (FAILED) or 0xFE (INVALID)
                GPIO.output(pin, GPIO.LOW)
                self.light_statuses[light] = 0  # Treat as OFF for database
            status_name = STATUS_NAMES.get(status_code, f"Unknown code: {hex(status_code)}")
            logging.info(f"Controlled LED: {light} = {status_name} ({hex(status_code)})")
    
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
                    
                    if light in LED_PINS:
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
        if self.bus:
            self.bus.shutdown()
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        GPIO.cleanup()
        logging.info("Shutdown complete")

if __name__ == "__main__":
    slave = CANLightSlave()
    slave.receive_messages()