#!/usr/bin/env python3
import can
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

class CANWiperSlave:
    def __init__(self):
        # Initialize CAN
        try:
            os.system('sudo /sbin/ip link set can0 up type can bitrate 500000')
            time.sleep(0.1)
            self.can_bus = can.interface.Bus(channel='can0', bustype='socketcan')
        except Exception as e:
            logging.error(f"CAN initialization failed: {e}")
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
        
        # Initialize response signals
        self.response_signals = self.read_response_file()
        
        # Start CAN monitoring thread
        self.can_thread = threading.Thread(target=self.monitor_can, daemon=True)
        self.can_thread.start()
        
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
        """Create CAN frame for response signals"""
        data = bytearray(8)
        # WiperStatus: 1 if no block or error, else 0
        wiper_status = 1 if (self.response_signals['isWiperBlocked'] == 0 and 
                            self.response_signals['hwError'] == 0) else 0
        data[0] = wiper_status
        data[1] = self.wiper_speed  # wiperCurrentSpeed
        data[2] = self.wiper_position  # wiperCurrentPosition
        data[3] = self.wiper_mode  # currentWiperMode
        data[4] = self.response_signals['consumedPower']
        data[5] = self.response_signals['isWiperBlocked']
        data[6] = self.response_signals['blockageReason']
        data[7] = self.response_signals['hwError']
        return data

    def send_response(self):
        """Send response signals back to master"""
        try:
            data = self.create_response_frame()
            msg = can.Message(
                arbitration_id=0x101,
                data=data,
                is_extended_id=False
            )
            self.can_bus.send(msg)
            logging.info(f"Sent response CAN: {data.hex()}")
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
            logging.error(f"CAN response send error: {e}")

    def process_can_signals(self, signals):
        """Process received CAN signals and control wipers accordingly"""
        logging.info(f"Processing signals: {signals}")
        
        self._stop_wipers()
        
        self.wiper_mode = signals.get('wiperMode', 0)
        self.wiper_speed = signals.get('wiperSpeed', 1)
        self.wiper_intermittent = signals.get('WiperIntermittent', 0)
        
        if self.wiper_mode == 0:
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

    def parse_can_frame(self, data):
        """Convert CAN data back to signals"""
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
        return signals

    def monitor_can(self):
        """Monitor CAN bus for messages"""
        logging.info("Listening for CAN messages...")
        try:
            while self.running:
                msg = self.can_bus.recv(timeout=1.0)
                if msg and msg.arbitration_id == 0x100:
                    signals = self.parse_can_frame(msg.data)
                    self.process_can_signals(signals)
        except Exception as e:
            logging.error(f"CAN monitoring error: {e}")

    def shutdown(self):
        """Clean up resources"""
        logging.info("Shutting down...")
        self.running = False
        self._stop_wipers()
        
        if self.can_thread.is_alive():
            self.can_thread.join(timeout=0.5)
        if self.response_thread.is_alive():
            self.response_thread.join(timeout=0.5)
        
        if self.can_bus:
            self.can_bus.shutdown()
        os.system('sudo /sbin/ip link set can0 down')
        GPIO.cleanup()
        logging.info("Shutdown complete")

if __name__ == "__main__":
    try:
        slave = CANWiperSlave()
        while slave.running:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    finally:
        slave.shutdown()