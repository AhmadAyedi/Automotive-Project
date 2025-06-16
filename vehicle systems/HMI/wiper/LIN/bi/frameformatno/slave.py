#!/usr/bin/env python3
import serial
import os
import RPi.GPIO as GPIO
import time
import threading
import logging
import re

# GPIO setup
FRONT_LEDS = [23, 24, 26]  # Right to left
BACK_LEDS = [16, 20, 21]   # Right to left

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('wiper_slave_lin.log'),
        logging.StreamHandler()
    ]
)

class LINWiperSlave:
    def __init__(self):
        # Initialize LIN interface
        self.serial_port = '/dev/serial0'
        self.baudrate = 9600
        self.ser = None
        
        # GPIO setup
        GPIO.setmode(GPIO.BCM)
        for pin in FRONT_LEDS + BACK_LEDS:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
            
        # Thread control
        self.stop_event = threading.Event()
        self.active_threads = []
        self.operation_lock = threading.Lock()
        self.running = True
        self.back_wiper_active = False
        
        # Signal storage
        self.wiper_mode = 0
        self.wiper_speed = 1
        self.wiper_intermittent = 0
        self.wiper_position = 0
        self.response_last_modified = 0
        self.wiper_function_enabled = 1
        
        # LIN frame IDs (PIDs)
        self.MASTER_REQUEST_PID = 0x30
        self.SLAVE_RESPONSE_PID = 0x31
        
        # Initialize response signals
        self.response_signals = self.read_response_file()
        
        try:
            self.init_lin_interface()
            # Start LIN monitoring thread
            self.lin_thread = threading.Thread(target=self.monitor_lin, daemon=True)
            self.lin_thread.start()
            
            # Start response file monitoring thread
            self.start_response_monitor()
            
            logging.info("Wiper slave (LIN) initialized")
        except Exception as e:
            logging.error(f"Initialization failed: {e}")
            self.shutdown()
            raise

    def init_lin_interface(self):
        """Initialize the serial interface with improved settings"""
        try:
            # Enable UART and disable Bluetooth
            os.system('sudo raspi-config nonint do_serial 0')
            os.system('sudo dtoverlay disable-bt')
            os.system('sudo systemctl disable hciuart')
            
            # Ensure port permissions
            if os.path.exists(self.serial_port):
                os.system(f'sudo chmod 777 {self.serial_port}')
            
            self.ser = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=0.1,
                inter_byte_timeout=0.01
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            logging.info(f"LIN interface initialized on {self.serial_port}")
        except Exception as e:
            logging.error(f"LIN init failed: {e}")
            raise

    def calculate_checksum(self, pid, data):
        """Calculate LIN classic checksum (for LIN 1.x)"""
        checksum = pid
        for byte in data:
            checksum += byte
            if checksum > 0xFF:
                checksum -= 0xFF
        checksum = (~checksum) & 0xFF
        return checksum

    def read_response_file(self):
        """Read response signals from response.txt"""
        defaults = {
            'consumedPower': 111,
            'isWiperBlocked': 0,
            'blockageReason': 0,
            'hwError': 0
        }
        try:
            with open("response.txt", 'r') as f:
                content = f.read()
                signals = {}
                matches = re.finditer(r'(\w+)\s*=\s*(\d+)', content)
                for match in matches:
                    signals[match.group(1)] = int(match.group(2))
                # Ensure all required signals are present
                for key, value in defaults.items():
                    if key not in signals:
                        signals[key] = value
                return signals
        except FileNotFoundError:
            logging.warning("response.txt not found, using defaults")
            return defaults
        except Exception as e:
            logging.error(f"Error reading response.txt: {e}")
            return defaults

    def response_file_changed(self):
        """Check if response.txt has been modified"""
        try:
            mod_time = os.path.getmtime("response.txt")
            if mod_time != self.response_last_modified:
                self.response_last_modified = mod_time
                return True
            return False
        except:
            return False

    def monitor_response_file(self):
        """Monitor response.txt for changes"""
        logging.info("Monitoring response.txt...")
        try:
            while self.running:
                if self.response_file_changed():
                    logging.info("response.txt changed, updating signals")
                    self.response_signals = self.read_response_file()
                    print("\nUpdated Response Signals from response.txt:")
                    for key, value in self.response_signals.items():
                        print(f"{key}: {value}")
                    self.send_response()
                time.sleep(0.3)
        except Exception as e:
            logging.error(f"Response file monitoring error: {e}")

    def start_response_monitor(self):
        """Start response file monitoring thread"""
        self.response_thread = threading.Thread(target=self.monitor_response_file, daemon=True)
        self.response_thread.start()

    def create_lin_frame(self, pid, data):
        """Create a complete LIN frame"""
        # Ensure data is exactly 8 bytes
        if len(data) < 8:
            data = data + bytes([0] * (8 - len(data)))
        elif len(data) > 8:
            data = data[:8]
            
        checksum = self.calculate_checksum(pid, data)
        
        # Build frame
        frame = bytearray()
        frame.append(0x00)  # Break
        frame.append(0x55)  # Sync
        frame.append(pid)   # PID
        frame.extend(data)  # Data
        frame.append(checksum)  # Checksum
        
        return frame

    def send_lin_frame(self, pid, data):
        """Send a LIN frame with proper timing"""
        frame = self.create_lin_frame(pid, data)
        try:
            # Clear buffers before sending
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            # Send with small delays between bytes
            for byte in frame:
                self.ser.write(bytes([byte]))
                time.sleep(0.001)
            
            logging.info(f"Sent LIN frame: PID={hex(pid)}, Data={bytes(data).hex()}, Checksum={hex(frame[-1])}")
        except Exception as e:
            logging.error(f"LIN send error: {e}")

    def _wiper_sweep(self, leds, speed, stop_event):
        """Perform a wiper sweep with timing"""
        delay = 0.3  # Base delay for normal speed
        if speed == 2:  # Fast speed
            delay = 0.15
        
        # Simulate position from 0 to 100
        steps = len(leds) * 2  # Forward and backward
        position_increment = 100 // steps
        
        # Forward sweep
        for i, led in enumerate(leds):
            if stop_event.is_set():
                return False
            GPIO.output(led, GPIO.HIGH)
            self.wiper_position = min(100, self.wiper_position + position_increment)
            time.sleep(delay/len(leds))
        
        # Backward sweep
        for i, led in enumerate(reversed(leds)):
            if stop_event.is_set():
                return False
            GPIO.output(led, GPIO.LOW)
            self.wiper_position = max(0, self.wiper_position - position_increment)
            time.sleep(delay/len(leds))
        
        return True

    def _activate_wiper(self, leds, speed, cycles, is_intermittent=False):
        """Wiper operation with stop capability"""
        count = 0
        
        try:
            while cycles == 0 or count < cycles:
                if self.stop_event.is_set():
                    break
                
                if not self._wiper_sweep(leds, speed, self.stop_event):
                    break
                
                if cycles > 0:
                    count += 1
                
                if is_intermittent:
                    if not (self.wiper_mode == 2 and 
                           self.wiper_speed == 1 and 
                           self.wiper_intermittent == 1):
                        break
                    time.sleep(1.7)
        finally:
            for led in leds:
                GPIO.output(led, GPIO.LOW)
            self.wiper_position = 0
            self.send_response()

    def _stop_wipers(self):
        """Immediately stop all wiper activity"""
        with self.operation_lock:
            self.stop_event.set()
            
            for t in self.active_threads:
                t.join(timeout=0.1)
            
            for pin in FRONT_LEDS + BACK_LEDS:
                GPIO.output(pin, GPIO.LOW)
            
            self.stop_event.clear()
            self.active_threads = []
            self.back_wiper_active = False
            self.wiper_position = 0
            logging.info("Wipers fully stopped")
            self.send_response()

    def create_response_data(self):
        """Create LIN data payload for response signals"""
        data = bytearray(8)
        # WiperStatus: 1 if no block, no error, and enabled
        wiper_status = 1 if (self.response_signals['isWiperBlocked'] == 0 and 
                             self.response_signals['hwError'] == 0 and 
                             self.wiper_function_enabled == 1) else 0
        data[0] = wiper_status
        data[1] = 0 if self.wiper_function_enabled == 0 else self.wiper_speed
        data[2] = self.wiper_position
        data[3] = self.wiper_mode
        data[4] = self.response_signals['consumedPower']
        data[5] = self.response_signals['isWiperBlocked']
        data[6] = self.response_signals['blockageReason']
        data[7] = self.response_signals['hwError']
        return data

    def send_response(self):
        """Send response signals back to master"""
        try:
            data = self.create_response_data()
            self.send_lin_frame(self.SLAVE_RESPONSE_PID, data)
            
            # Display sent signals
            signals = {
                'WiperStatus': data[0],
                'wiperCurrentSpeed': data[1],
                'wiperCurrentPosition': data[2],
                'currentWiperMode': data[3],
                'consumedPower': data[4],
                'isWiperBlocked': data[5],
                'blockageReason': data[6],
                'hwError': data[7]
            }
            print("\nSent Response Signals:")
            for key, value in signals.items():
                print(f"{key}: {value}")
        except Exception as e:
            logging.error(f"LIN response send error: {e}")

    def process_signals(self, signals):
        """Process received signals and control wipers"""
        logging.info(f"Processing signals: {signals}")
        
        self._stop_wipers()
        
        self.wiper_mode = signals.get('wiperMode', 0)
        self.wiper_speed = signals.get('wiperSpeed', 1)
        self.wiper_intermittent = signals.get('WiperIntermittent', 0)
        self.wiper_function_enabled = signals.get('Wiper_Function_Enabled', 1)
        
        if self.wiper_mode == 0 or self.wiper_function_enabled == 0:
            self.send_response()
            return
        
        if self.wiper_mode == 1:
            thread = threading.Thread(
                target=self._activate_wiper,
                args=(FRONT_LEDS, self.wiper_speed, 1),
                daemon=True
            )
            self.active_threads = [thread]
            thread.start()
            logging.info("Started touch mode (single wipe)")
        
        elif self.wiper_mode in [2, 4]:
            front_thread = threading.Thread(
                target=self._activate_wiper,
                args=(FRONT_LEDS, self.wiper_speed, 0),
                daemon=True
            )
            self.active_threads = [front_thread]
            front_thread.start()
            
            if (self.wiper_mode == 2 and 
                self.wiper_speed == 1 and 
                self.wiper_intermittent == 1):
                self.back_wiper_active = True
                back_thread = threading.Thread(
                    target=self._activate_wiper,
                    args=(BACK_LEDS, 1, 0, True),
                    daemon=True
                )
                self.active_threads.append(back_thread)
                back_thread.start()
                logging.info("Started intermittent rear wiper")
            else:
                with self.operation_lock:
                    for led in BACK_LEDS:
                        GPIO.output(led, GPIO.LOW)
                logging.debug("Ensured rear wipers are off")
            
            logging.info(f"Started continuous front wiper (speed={'fast' if self.wiper_speed == 2 else 'normal'})")
        
        self.send_response()

    def parse_request_data(self, data):
        """Convert LIN data back to signals"""
        signals = {}
        if data[0] > 0:
            signals['wiperMode'] = data[0]
        if data[1] > 0:
            signals['wiperSpeed'] = data[1]
        if data[2] > 0:
            signals['wiperCycleCount'] = data[2]
        if data[3] > 0:
            signals['WiperIntermittent'] = data[3]
        if data[4] > 0 or data[5] > 0:
            signals['wipingCycle'] = data[4] | (data[5] << 8)
        signals['Wiper_Function_Enabled'] = data[6]
        return signals

    def monitor_lin(self):
        """Monitor LIN bus for messages from master"""
        logging.info("Listening for LIN messages...")
        buffer = bytearray()
        
        try:
            while self.running:
                # Read available data
                data = self.ser.read(self.ser.in_waiting or 1)
                if data:
                    buffer.extend(data)
                    logging.debug(f"Raw data received: {bytes(data).hex()}")
                    
                    # Process complete frames in buffer
                    while len(buffer) >= 11:  # sync + pid + 8 data + checksum
                        # Find sync byte
                        sync_pos = -1
                        for i, byte in enumerate(buffer):
                            if byte == 0x55:
                                sync_pos = i
                                break
                        
                        if sync_pos == -1:
                            buffer.clear()
                            continue
                        
                        # Check if we have a complete frame
                        if len(buffer) >= sync_pos + 11:
                            frame = buffer[sync_pos:sync_pos+11]
                            pid = frame[1]
                            data = frame[2:10]
                            checksum = frame[10]
                            
                            # Verify checksum
                            calculated = self.calculate_checksum(pid, data)
                            if checksum == calculated:
                                if pid == self.MASTER_REQUEST_PID:
                                    signals = self.parse_request_data(data)
                                    self.process_signals(signals)
                                buffer = buffer[sync_pos+11:]
                            else:
                                logging.error(f"Checksum error: expected {hex(calculated)}, got {hex(checksum)}")
                                buffer = buffer[sync_pos+1:]
                        else:
                            break
                
                time.sleep(0.01)
        except Exception as e:
            logging.error(f"LIN monitoring error: {e}")

    def shutdown(self):
        """Clean up resources"""
        logging.info("Shutting down...")
        self.running = False
        self._stop_wipers()
        
        if hasattr(self, 'lin_thread') and self.lin_thread.is_alive():
            self.lin_thread.join(timeout=0.5)
        if hasattr(self, 'response_thread') and self.response_thread.is_alive():
            self.response_thread.join(timeout=0.5)
        
        if self.ser and self.ser.is_open:
            self.ser.close()
        GPIO.cleanup()
        logging.info("Shutdown complete")

if __name__ == "__main__":
    try:
        slave = LINWiperSlave()
        while slave.running:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        if 'slave' in locals():
            slave.shutdown()