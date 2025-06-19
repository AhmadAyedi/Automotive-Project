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
        logging.FileHandler('wiper_slave.log'),
        logging.StreamHandler()
    ]
)

class UARTWiperSlave:
    def __init__(self):
        # Initialize UART
        try:
            self.serial = serial.Serial(
                port='/dev/serial0',
                baudrate=115200,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=1
            )
            logging.info("UART initialized")
        except Exception as e:
            logging.error(f"UART initialization failed: {e}")
            raise
        
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
        self.wiper_function_enabled = 1  # Default to enabled
        
        # Initialize response signals
        self.response_signals = self.read_response_file()
        
        # Start UART monitoring thread
        self.uart_thread = threading.Thread(target=self.monitor_uart, daemon=True)
        self.uart_thread.start()
        
        # Start response file monitoring thread
        self.start_response_monitor()
        
        logging.info("Wiper slave initialized")

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
        """Monitor response.txt for changes and send updates"""
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
                time.sleep(0.3)  # Fast polling
        except Exception as e:
            logging.error(f"Response file monitoring error: {e}")

    def start_response_monitor(self):
        """Start a thread to monitor response.txt"""
        self.response_thread = threading.Thread(target=self.monitor_response_file, daemon=True)
        self.response_thread.start()

    def _wiper_sweep(self, leds, speed, stop_event):
        """Perform a complete wiper sweep with proper timing"""
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
        """Wiper operation with immediate stop capability"""
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

    def create_response_frame(self):
        """Create UART frame for response signals"""
        # Format: <STX>WiperStatus,wiperCurrentSpeed,wiperCurrentPosition,currentWiperMode,consumedPower,isWiperBlocked,blockageReason,hwError<ETX>
        # WiperStatus: 1 if no block, no error, and Wiper_Function_Enabled = 1, else 0
        wiper_status = 1 if (self.response_signals['isWiperBlocked'] == 0 and 
                             self.response_signals['hwError'] == 0 and 
                             self.wiper_function_enabled == 1) else 0
        frame = f"<STX>{wiper_status}," \
                f"{0 if self.wiper_function_enabled == 0 else self.wiper_speed}," \
                f"{self.wiper_position}," \
                f"{self.wiper_mode}," \
                f"{self.response_signals['consumedPower']}," \
                f"{self.response_signals['isWiperBlocked']}," \
                f"{self.response_signals['blockageReason']}," \
                f"{self.response_signals['hwError']}<ETX>"
        return frame.encode('utf-8')

    def send_response(self):
        """Send response signals back to master"""
        try:
            data = self.create_response_frame()
            self.serial.write(data)
            logging.info(f"Sent response UART: {data.decode('utf-8')}")
            # Display sent signals
            signals = {
                'WiperStatus': int(data.decode('utf-8').split(',')[0][5:]) if data else 0,
                'wiperCurrentSpeed': int(data.decode('utf-8').split(',')[1]) if data else 0,
                'wiperCurrentPosition': int(data.decode('utf-8').split(',')[2]) if data else 0,
                'currentWiperMode': int(data.decode('utf-8').split(',')[3]) if data else 0,
                'consumedPower': int(data.decode('utf-8').split(',')[4]) if data else 0,
                'isWiperBlocked': int(data.decode('utf-8').split(',')[5]) if data else 0,
                'blockageReason': int(data.decode('utf-8').split(',')[6]) if data else 0,
                'hwError': int(data.decode('utf-8').split(',')[7][:-5]) if data else 0
            }
            print("\nSent Response Signals:")
            for key, value in signals.items():
                print(f"{key}: {value}")
        except Exception as e:
            logging.error(f"UART response send error: {e}")

    def parse_uart_frame(self, data):
        """Convert UART data back to signals"""
        try:
            decoded = data.decode('utf-8').strip()
            if not decoded.startswith("<STX>") or not decoded.endswith("<ETX>"):
                return None
                
            values = decoded[5:-5].split(',')
            if len(values) != 6:
                return None
                
            signals = {
                'wiperMode': int(values[0]),
                'wiperSpeed': int(values[1]),
                'wiperCycleCount': int(values[2]),
                'WiperIntermittent': int(values[3]),
                'wipingCycle': int(values[4]),
                'Wiper_Function_Enabled': int(values[5])
            }
            return signals
        except Exception as e:
            logging.error(f"Error parsing UART frame: {e}")
            return None

    def process_uart_signals(self, signals):
        """Process received UART signals and control wipers accordingly"""
        if not signals:
            return
            
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

    def monitor_uart(self):
        """Monitor UART for messages"""
        logging.info("Listening for UART messages...")
        try:
            while self.running:
                data = self.serial.read_until(b'<ETX>')
                if data:
                    signals = self.parse_uart_frame(data)
                    if signals:
                        self.process_uart_signals(signals)
        except Exception as e:
            logging.error(f"UART monitoring error: {e}")

    def shutdown(self):
        """Clean up resources"""
        logging.info("Shutting down...")
        self.running = False
        self._stop_wipers()
        
        if self.uart_thread.is_alive():
            self.uart_thread.join(timeout=0.5)
        if self.response_thread.is_alive():
            self.response_thread.join(timeout=0.5)
        
        if self.serial and self.serial.is_open:
            self.serial.close()
        GPIO.cleanup()
        logging.info("Shutdown complete")

if __name__ == "__main__":
    try:
        slave = UARTWiperSlave()
        while slave.running:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    finally:
        slave.shutdown()