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
            
    def _activate_single_wiper(self, leds, speed, cycles):
        """Activate a single wiper (front or back)"""
        delay = 0.3 if speed == 2 else 0.6  # Fast=0.3s, Normal=0.6s
        
        for _ in range(cycles):
            # Forward sweep
            for led in leds:
                GPIO.output(led, GPIO.HIGH)
                time.sleep(delay)
            
            # Backward sweep
            for led in reversed(leds):
                GPIO.output(led, GPIO.LOW)
                time.sleep(delay)
    
    def _stop_wipers(self):
        """Turn off all wiper LEDs"""
        for pin in FRONT_LEDS + BACK_LEDS:
            GPIO.output(pin, GPIO.LOW)
        logging.info("Stopped all wipers")
    
    def activate_wipers(self, wiper_type, speed, cycles):
        """Handle wiper activation with parallel support"""
        if wiper_type == 0:  # Stop command
            self._stop_wipers()
        elif wiper_type == 3:  # Both wipers in parallel
            front_thread = threading.Thread(
                target=self._activate_single_wiper,
                args=(FRONT_LEDS, speed, cycles)
            )
            back_thread = threading.Thread(
                target=self._activate_single_wiper,
                args=(BACK_LEDS, speed, cycles)
            )
            
            front_thread.start()
            back_thread.start()
            
            front_thread.join()
            back_thread.join()
        else:
            leds = FRONT_LEDS if wiper_type == 1 else BACK_LEDS
            self._activate_single_wiper(leds, speed, cycles)
    
    def run(self):
        try:
            while True:
                try:
                    frame = self.lin_slave.receive_frame(expected_data_length=3)
                    if frame:
                        frame_id, data = frame
                        if frame_id == 0x20 and len(data) == 3:
                            logging.info(f"Received frame: wiper_type={data[0]}, speed={data[1]}, cycles={data[2]}")
                            self.activate_wipers(data[0], data[1], data[2])
                            
                except Exception as e:
                    logging.error(f"Error: {e}")
                    time.sleep(0.1)
                    
        except KeyboardInterrupt:
            logging.info("\nShutting down...")
        finally:
            self.lin_slave.close()
            GPIO.cleanup()

if __name__ == "__main__":
    slave = WiperSlave()
    slave.run()