import serial
import RPi.GPIO as GPIO
import time
import threading
import logging
from collections import defaultdict

# LIN Frame IDs for each window type
WINDOW_IDS = {
    "DR": 0x10,
    "PS": 0x11,
    "DRS": 0x12,
    "PRS": 0x13
}

# Response IDs (same as window IDs for two-way communication)
RESPONSE_IDS = {
    "DR": 0x10,
    "PS": 0x11,
    "DRS": 0x12,
    "PRS": 0x13
}

# GPIO pins for each window's LEDs
WINDOW_LEDS = {
    "DR": [2, 3, 23, 17],
    "PS": [27, 22, 0, 5],
    "DRS": [6, 13, 19, 26],
    "PRS": [12, 16, 20, 21]
}

# Status indicator LEDs
RED_LED = 18
GREEN_LED = 24
YELLOW_LED = 7

# Result codes
RESULT_CODES = ["OP", "CL", "OPG", "CLG", "FOP", "OP_D", "CL_D", "OPG_D", "CLG_D", "FOP_D", 
                "OP_AD", "CL_AD", "OPG_AD", "CLG_AD", "FOP_AD", "OP_A", "CL_A", "OPG_A", "CLG_A", "FOP_A", "FAILED"]

# Level types and modes
LEVEL_TYPES = ["AUTO", "MANUAL"]
MODES = ["WHONEN", "FAHREN"]

# LIN Constants
SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 19200
WAKEUP_PIN = 1
SYNC_BYTE = 0x55
BREAK_BYTE = 0x00

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('window_slave.log'),
        logging.StreamHandler()
    ]
)

class LINWindowSlave:
    def __init__(self):
        self.running = True
        self.window_status = {
            "DR": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN", "safety": "OFF"},
            "PS": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN", "safety": "OFF"},
            "DRS": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN", "safety": "OFF"},
            "PRS": {"level": 0, "result": "CL", "level_type": "AUTO", "mode": "WHONEN", "safety": "OFF"}
        }
        self.current_led_states = defaultdict(int)
        self.lock = threading.Lock()
        
        # Initialize GPIO and serial
        self.setup_gpio()
        self.ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=0.1)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(WAKEUP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        logging.info("Window slave initialized")
    
    def setup_gpio(self):
        """Initialize all GPIO pins for window LEDs and status indicators"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup window LEDs
        for leds in WINDOW_LEDS.values():
            for pin in leds:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
        
        # Setup status indicator LEDs
        GPIO.setup(RED_LED, GPIO.OUT)
        GPIO.setup(GREEN_LED, GPIO.OUT)
        GPIO.setup(YELLOW_LED, GPIO.OUT)
        GPIO.output(RED_LED, GPIO.LOW)
        GPIO.output(GREEN_LED, GPIO.HIGH)  # Start with green LED on by default
        GPIO.output(YELLOW_LED, GPIO.LOW)  # Yellow LED off by default
        
        logging.info("GPIO initialized")
    
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
    
    def send_break(self):
        self.ser.baudrate = BAUD_RATE // 4
        self.ser.write(bytes([BREAK_BYTE]))
        self.ser.flush()
        time.sleep(13 * (1.0 / (BAUD_RATE // 4)))
        self.ser.baudrate = BAUD_RATE
    
    def send_lin_response(self, window, status):
        """Send a complete LIN response frame"""
        try:
            self.send_break()
            self.ser.write(bytes([SYNC_BYTE]))
            
            pid = self.calculate_pid(RESPONSE_IDS[window])
            self.ser.write(bytes([pid]))
            
            # Prepare response data (5 bytes)
            msg_data = bytes([
                RESULT_CODES.index(status["result"]),
                status["level"],
                LEVEL_TYPES.index(status["level_type"]),
                MODES.index(status["mode"]),
                1 if status["safety"] == "ON" else 0
            ])
            
            self.ser.write(msg_data)
            
            # Calculate and send checksum
            checksum = self.calculate_checksum(pid, msg_data)
            self.ser.write(bytes([checksum]))
            self.ser.flush()
            
            logging.info(f"Sent response for {window}: {status}")
        except Exception as e:
            logging.error(f"Error sending LIN response: {e}")
    
    def update_status_leds(self, result, safety):
        """Update the status LEDs based on the result code and safety status"""
        # First turn off all status LEDs
        GPIO.output(RED_LED, GPIO.LOW)
        GPIO.output(GREEN_LED, GPIO.LOW)
        GPIO.output(YELLOW_LED, GPIO.LOW)
        
        if result == "FAILED":
            GPIO.output(YELLOW_LED, GPIO.HIGH)
            logging.info("FAILED status detected, turning on yellow LED")
        elif safety == "ON":
            GPIO.output(RED_LED, GPIO.HIGH)
            logging.info("Safety ON detected, turning on red LED")
        else:
            GPIO.output(GREEN_LED, GPIO.HIGH)
            logging.info("Normal operation, turning on green LED")
    
    def get_required_leds(self, level):
        """Determine how many LEDs should be on based on window level"""
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
        """Update the LEDs for a specific window based on its level"""
        required_leds = self.get_required_leds(new_level)
        current_leds = self.current_led_states[window]
        leds = WINDOW_LEDS[window]
        
        logging.info(f"Updating {window} from {current_leds} LEDs to {required_leds} LEDs (Level: {new_level}%)")
        
        if required_leds > current_leds:
            for i in range(current_leds, required_leds):
                GPIO.output(leds[i], GPIO.HIGH)
                logging.info(f"Turned on {window} LED {i+1} (GPIO {leds[i]})")
                time.sleep(1)
        elif required_leds < current_leds:
            for i in range(current_leds-1, required_leds-1, -1):
                GPIO.output(leds[i], GPIO.LOW)
                logging.info(f"Turned off {window} LED {i+1} (GPIO {leds[i]})")
                time.sleep(1)
        
        with self.lock:
            self.current_led_states[window] = required_leds
            self.window_status[window]["level"] = new_level
    
    def handle_window_command(self, window, result, level, level_type, mode, safety):
        """Process a window control command from master"""
        # First update the status LEDs based on the result and safety
        self.update_status_leds(result, safety)
        
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
        with self.lock:
            self.send_lin_response(window, self.window_status[window])
    
    def process_frame(self, buffer):
        """Process a complete LIN frame from the buffer"""
        try:
            # Verify break and sync
            if buffer[0] != BREAK_BYTE or buffer[1] != SYNC_BYTE:
                logging.warning("Invalid frame start (missing break or sync)")
                return False
            
            if len(buffer) < 9:  # Need at least break(1) + sync(1) + pid(1) + data(5) + checksum(1)
                logging.warning("Incomplete frame received")
                return False
            
            pid = buffer[2]
            frame_id = pid & 0x3F
            window = next((name for name, wid in WINDOW_IDS.items() if wid == frame_id), None)
            
            if not window:
                logging.warning(f"Received frame for unknown window ID: {frame_id}")
                return False
            
            data = buffer[3:8]
            received_checksum = buffer[8]
            
            # Verify checksum
            calc_checksum = self.calculate_checksum(pid, data)
            
            if received_checksum != calc_checksum:
                logging.warning(f"Checksum mismatch for {window}: received {hex(received_checksum)}, calculated {hex(calc_checksum)}")
                return False
            
            # Process the data
            result_index = data[0]
            level = data[1]
            level_type_idx = data[2]
            mode_idx = data[3]
            safety = "ON" if data[4] == 1 else "OFF"
            
            if (0 <= result_index < len(RESULT_CODES)) and \
               (0 <= level <= 100) and \
               (0 <= level_type_idx < len(LEVEL_TYPES)) and \
               (0 <= mode_idx < len(MODES)):
                
                result = RESULT_CODES[result_index]
                level_type = LEVEL_TYPES[level_type_idx]
                mode = MODES[mode_idx]
                
                logging.info(f"Received command for {window}: {result} | {level}% | {level_type} | {mode} | safety_{safety}")
                threading.Thread(
                    target=self.handle_window_command,
                    args=(window, result, level, level_type, mode, safety),
                    daemon=True
                ).start()
                return True
            else:
                logging.error("Invalid data in received frame")
                return False
            
        except (IndexError, ValueError) as e:
            logging.error(f"Error processing frame: {e}")
            return False
    
    def receive_messages(self):
        """Main loop to receive and process LIN messages"""
        buffer = bytearray()
        logging.info("LIN Window Slave - Listening for frames...")
        
        try:
            while self.running:
                if self.ser.in_waiting:
                    byte = self.ser.read(1)
                    if byte:
                        buffer += byte
                    
                    # Check if we have a complete frame (break + sync + pid + 5 data + checksum)
                    if len(buffer) >= 9:
                        if self.process_frame(buffer):
                            buffer = buffer[9:]  # Remove processed frame from buffer
                        else:
                            buffer = bytearray()  # Invalid frame, clear buffer
                time.sleep(0.001)
                
        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt")
        except Exception as e:
            logging.error(f"Error in receive_messages: {e}")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Cleanup resources"""
        logging.info("Shutting down...")
        self.running = False
        
        # Turn off all LEDs during shutdown
        for leds in WINDOW_LEDS.values():
            for pin in leds:
                GPIO.output(pin, GPIO.LOW)
        GPIO.output(RED_LED, GPIO.LOW)
        GPIO.output(GREEN_LED, GPIO.LOW)
        GPIO.output(YELLOW_LED, GPIO.LOW)
        
        if self.ser:
            self.ser.close()
        GPIO.cleanup()
        logging.info("Shutdown complete")

if __name__ == "__main__":
    slave = LINWindowSlave()
    slave.receive_messages()