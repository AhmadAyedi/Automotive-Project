#!/usr/bin/env python3
from lin_protocol import LINSlave
import RPi.GPIO as GPIO
import time
import logging
import threading

# GPIO setup
FRONT_LEDS = [23, 24, 25]  # Right to left
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

class WiperSlave:
    def __init__(self):
        self.lin_slave = LINSlave()
        GPIO.setmode(GPIO.BCM)
        for pin in FRONT_LEDS + BACK_LEDS:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        self.stop_event = threading.Event()
        self.active_threads = []
        self.operation_lock = threading.Lock()
            
    def _activate_single_wiper(self, leds, speed, cycles):
        """Wiper operation with immediate stop capability"""
        delay = 0.3 if speed == 2 else 0.6
        
        for _ in range(cycles):
            if self.stop_event.is_set():
                break
                
            # Forward sweep with frequent stop checks
            for led in leds:
                if self.stop_event.is_set():
                    break
                GPIO.output(led, GPIO.HIGH)
                start_time = time.time()
                while time.time() - start_time < delay:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.05)  # Check every 50ms
            
            # Backward sweep with frequent stop checks
            for led in reversed(leds):
                if self.stop_event.is_set():
                    break
                GPIO.output(led, GPIO.LOW)
                start_time = time.time()
                while time.time() - start_time < delay:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.05)
    
    def _stop_wipers(self):
        """Immediately stop all wiper activity"""
        with self.operation_lock:
            self.stop_event.set()
            
            # Wait for active threads to finish
            for t in self.active_threads:
                t.join(timeout=0.1)
            
            # Ensure all LEDs are off
            for pin in FRONT_LEDS + BACK_LEDS:
                GPIO.output(pin, GPIO.LOW)
            
            self.stop_event.clear()
            self.active_threads = []
            logging.info("Wipers fully stopped")
    
    def activate_wipers(self, wiper_type, speed, cycles):
        """Handle wiper commands with immediate stop capability"""
        # First stop any existing operations
        self._stop_wipers()
        
        if wiper_type == 0:  # Explicit stop command
            return
            
        # Prepare new operation
        if wiper_type == 3:  # Both wipers
            front_thread = threading.Thread(
                target=self._activate_single_wiper,
                args=(FRONT_LEDS, speed, cycles)
            )
            back_thread = threading.Thread(
                target=self._activate_single_wiper,
                args=(BACK_LEDS, speed, cycles)
            )
            self.active_threads = [front_thread, back_thread]
            front_thread.start()
            back_thread.start()
        else:  # Single wiper
            leds = FRONT_LEDS if wiper_type == 1 else BACK_LEDS
            single_thread = threading.Thread(
                target=self._activate_single_wiper,
                args=(leds, speed, cycles)
            )
            self.active_threads = [single_thread]
            single_thread.start()
    
    def run(self):
        try:
            logging.info("Starting wiper slave")
            while True:
                try:
                    frame = self.lin_slave.receive_frame(expected_data_length=3)
                    if frame:
                        frame_id, data = frame
                        if frame_id == 0x20 and len(data) == 3:
                            logging.info(f"Received command: type={data[0]}, speed={data[1]}, cycles={data[2]}")
                            if data == bytes([0, 0, 0]):
                                logging.info("Processing STOP command")
                                self._stop_wipers()
                            else:
                                self.activate_wipers(data[0], data[1], data[2])
                except Exception as e:
                    logging.error(f"Communication error: {e}")
                    time.sleep(0.1)
                    
        except KeyboardInterrupt:
            logging.info("Shutdown initiated")
        finally:
            self._stop_wipers()
            self.lin_slave.close()
            GPIO.cleanup()
            logging.info("Slave shutdown complete")

if __name__ == "__main__":
    slave = WiperSlave()
    slave.run()