#!/usr/bin/env python3
import can
import os
import RPi.GPIO as GPIO
import time
import threading
import logging

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
        
        # Start CAN monitoring thread
        self.can_thread = threading.Thread(target=self.monitor_can, daemon=True)
        self.can_thread.start()
        
        logging.info("Wiper slave initialized")

    def _wiper_sweep(self, leds, speed, stop_event):
        """Perform a complete wiper sweep with proper timing"""
        delay = 0.3  # Base delay for normal speed
        if speed == 2:  # Fast speed
            delay = 0.15
        
        # Forward sweep (right to left)
        for i, led in enumerate(leds):
            if stop_event.is_set():
                return False
            GPIO.output(led, GPIO.HIGH)
            time.sleep(delay/len(leds))
        
        # Backward sweep (left to right)
        for i, led in enumerate(reversed(leds)):
            if stop_event.is_set():
                return False
            GPIO.output(led, GPIO.LOW)
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
                
                # For intermittent mode, add additional delay
                if is_intermittent:
                    # Check if we should still be in intermittent mode
                    if not (self.wiper_mode == 2 and 
                           self.wiper_speed == 1 and 
                           self.wiper_intermittent == 1):
                        break
                    time.sleep(1.7)  # 1700ms delay
        finally:
            # Ensure all LEDs are off when done
            for led in leds:
                GPIO.output(led, GPIO.LOW)

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
            self.back_wiper_active = False
            logging.info("Wipers fully stopped")

    def process_can_signals(self, signals):
        """Process received CAN signals and control wipers accordingly"""
        logging.info(f"Processing signals: {signals}")
        
        # First stop any existing operations
        self._stop_wipers()
        
        # Get mode and parameters
        self.wiper_mode = signals.get('wiperMode', 0)
        self.wiper_speed = signals.get('wiperSpeed', 1)
        self.wiper_intermittent = signals.get('WiperIntermittent', 0)
        
        # Ignore if no valid mode
        if self.wiper_mode == 0:
            return
        
        # Touch mode (single wipe)
        if self.wiper_mode == 1:
            thread = threading.Thread(
                target=self._activate_wiper,
                args=(FRONT_LEDS, self.wiper_speed, 1),
                daemon=True
            )
            self.active_threads = [thread]
            thread.start()
            logging.info("Started touch mode (single wipe)")
        
        # Continuous modes (Speed1/Speed2/Automatic)
        elif self.wiper_mode in [2, 4]:
            # Front wiper continuous
            front_thread = threading.Thread(
                target=self._activate_wiper,
                args=(FRONT_LEDS, self.wiper_speed, 0),  # 0 = infinite cycles
                daemon=True
            )
            self.active_threads = [front_thread]
            front_thread.start()
            
            # Check if we should activate rear wiper
            if (self.wiper_mode == 2 and 
                self.wiper_speed == 1 and 
                self.wiper_intermittent == 1):
                self.back_wiper_active = True
                back_thread = threading.Thread(
                    target=self._activate_wiper,
                    args=(BACK_LEDS, 1, 0, True),  # Speed 1, infinite, intermittent
                    daemon=True
                )
                self.active_threads.append(back_thread)
                back_thread.start()
                logging.info("Started intermittent rear wiper")
            else:
                # Explicitly turn off rear wiper if conditions aren't met
                with self.operation_lock:
                    for led in BACK_LEDS:
                        GPIO.output(led, GPIO.LOW)
                logging.debug("Ensured rear wipers are off")
            
            logging.info(f"Started continuous front wiper (speed={'fast' if self.wiper_speed == 2 else 'normal'})")

    def parse_can_frame(self, data):
        """Convert CAN data back to signals"""
        signals = {}
        if data[0] > 0:  # wiperMode
            signals['wiperMode'] = data[0]
        if data[1] > 0:  # wiperSpeed
            signals['wiperSpeed'] = data[1]
        if data[2] > 0:  # wiperCycleCount
            signals['wiperCycleCount'] = data[2]
        if data[3] > 0:  # WiperIntermittent
            signals['WiperIntermittent'] = data[3]
        if data[4] > 0 or data[5] > 0:  # wipingCycle
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