#!/usr/bin/env python3
"""
Professional CAN Light Slave Controller with Correct LED Numbering (0-based)
FIXED VERSION - Corrected shift register data order
"""

import can
import RPi.GPIO as GPIO
import logging
import os
import time
import threading
import cantools

class CANLightSlave:
    def __init__(self):
        self.channel = 'can0'
        self.bustype = 'socketcan'
        self.bus = None
        self.running = True
        
        # GPIO Pins for 74HC595 (BOARD numbering)
        self.Latch = 13    # BOARD 13
        self.Clock = 15    # BOARD 15
        self.Serial_Input = 11  # BOARD 11
        self.Clear = 7     # BOARD 7
        
        # LED Groups using 0-based indexing (corrected order)
        self.LED_GROUPS = {
            "LOW_BEAM": [32, 23],      # LEDs 33,24 (0-based: 32,23)
            "HIGH_BEAM": [32, 23, 33, 0],  # LEDs 33,24,34,1 (0-based: 32,23,33,0)
            "PARKING_LEFT": [34, 35],   # LEDs 35,36 (0-based: 34,35)
            "PARKING_RIGHT": [39, 16],  # LEDs 40,17 (0-based: 39,16)
            "HAZARD_LIGHTS": [3, 31, 38, 37, 21, 20, 19, 18],  # LEDs 4,32,39,38,22,21,20,19
            "LEFT_TURN": {
                "group1": [3, 31],     # LEDs 4,32 (0-based: 3,31)
                "group2": [38, 37]     # LEDs 39,38 (0-based: 38,37)
            },
            "RIGHT_TURN": {
                "group1": [21, 20],    # LEDs 22,21 (0-based: 21,20)
                "group2": [19, 18]     # LEDs 20,19 (0-based: 19,18)
            }
        }
        
        # Mode indicator LEDs (0-based)
        self.MODE_LEDS = {
            "FAHREN": 4,    # LED 5 (0-based: 4)
            "STAND": 36,    # LED 37 (0-based: 36)
            "PARKING": 17,  # LED 18 (0-based: 17)
            "WOHNEN": 22    # LED 23 (0-based: 22)
        }
        
        # Load DBC file
        self.db = cantools.database.load_file('light_system.dbc')
        self.message_map = {
            "LOW_BEAM": self.db.get_message_by_name("LOW_BEAM_CTRL"),
            "HIGH_BEAM": self.db.get_message_by_name("HIGH_BEAM_CTRL"),
            "PARKING_LEFT": self.db.get_message_by_name("PARKING_LEFT_CTRL"),
            "PARKING_RIGHT": self.db.get_message_by_name("PARKING_RIGHT_CTRL"),
            "HAZARD_LIGHTS": self.db.get_message_by_name("HAZARD_LIGHTS_CTRL"),
            "RIGHT_TURN": self.db.get_message_by_name("RIGHT_TURN_CTRL"),
            "LEFT_TURN": self.db.get_message_by_name("LEFT_TURN_CTRL")
        }
        
        # Initialize light status
        self.light_status = {
            "LOW_BEAM": {"status": "OFF", "mode": "STAND", "should_be_on": False},
            "HIGH_BEAM": {"status": "OFF", "mode": "STAND"},
            "PARKING_LEFT": {"status": "OFF", "mode": "STAND"},
            "PARKING_RIGHT": {"status": "OFF", "mode": "STAND"},
            "HAZARD_LIGHTS": {"status": "OFF", "mode": "STAND"},
            "RIGHT_TURN": {"status": "OFF", "mode": "STAND"},
            "LEFT_TURN": {"status": "OFF", "mode": "STAND"}
        }
        
        self.current_mode = "STAND"
        self.leds_status = [0] * 40  # 0-based array for 40 LEDs
        self.hazard_thread = None
        self.left_turn_thread = None
        self.right_turn_thread = None
        self.hazard_running = False
        self.left_turn_running = False
        self.right_turn_running = False
        self.lock = threading.Lock()
        
        self.init_can_bus()
        self.setup_gpio()
        self.clear_register()
        self.shift_out(self.leds_status)
    
    def init_can_bus(self):
        """Initialize CAN bus interface"""
        try:
            os.system(f'sudo /sbin/ip link set {self.channel} up type can bitrate 500000')
            time.sleep(0.1)
            self.bus = can.interface.Bus(channel=self.channel, bustype=self.bustype)
            logging.info("CAN bus initialized successfully")
        except Exception as e:
            logging.error(f"CAN bus initialization failed: {e}")
            raise
    
    def setup_gpio(self):
        """Initialize GPIO pins using BOARD numbering"""
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)
        
        # Setup shift register pins
        GPIO.setup(self.Clock, GPIO.OUT)
        GPIO.setup(self.Latch, GPIO.OUT)
        GPIO.setup(self.Clear, GPIO.OUT)
        GPIO.setup(self.Serial_Input, GPIO.OUT)
        
        # Initialize states
        GPIO.output(self.Clock, GPIO.LOW)
        GPIO.output(self.Latch, GPIO.LOW)
        GPIO.output(self.Clear, GPIO.HIGH)
        GPIO.output(self.Serial_Input, GPIO.LOW)
        
        logging.info("GPIO initialized successfully")
    
    def clear_register(self):
        """Clear all LEDs in the shift register"""
        GPIO.output(self.Clear, 0)
        GPIO.output(self.Clear, 1)
        self.leds_status = [0] * 40
        logging.info("Shift register cleared")
    
    def shift_out(self, data):
        """Shift out data to the 74HC595 shift register (corrected order - LED 0 first)"""
        # Send data for all 40 LEDs in order (LED 0 first, LED 39 last)
        for state in data:
            GPIO.output(self.Serial_Input, state)
            GPIO.output(self.Clock, 1)
            GPIO.output(self.Clock, 0)
        
        # Latch the data to outputs
        GPIO.output(self.Latch, 1)
        GPIO.output(self.Latch, 0)
    
    def set_led(self, index, state):
        """Set a specific LED state (0-39)"""
        if 0 <= index < 40:
            self.leds_status[index] = 1 if state else 0
    
    def set_multiple_leds(self, indices, state):
        """Set multiple LEDs to the same state (indices 0-39)"""
        for index in indices:
            if 0 <= index < 40:
                self.leds_status[index] = 1 if state else 0
    
    def update_mode_leds(self, mode_name):
        """Update the mode indicator LEDs"""
        # Turn off all mode LEDs first
        for mode, led_index in self.MODE_LEDS.items():
            self.set_led(led_index, False)
        
        # Turn on the current mode LED
        if mode_name in self.MODE_LEDS:
            self.set_led(self.MODE_LEDS[mode_name], True)
            self.current_mode = mode_name
            logging.info(f"Mode indicator set to {mode_name}")
            
            # Special handling for Low Beam based on mode change
            if self.light_status["LOW_BEAM"]["should_be_on"]:
                if mode_name in ["FAHREN", "WOHNEN"]:
                    self.turn_on_light("LOW_BEAM")
                    self.light_status["LOW_BEAM"]["status"] = "ON"
                else:
                    self.turn_off_light("LOW_BEAM")
                    self.light_status["LOW_BEAM"]["status"] = "OFF"
        
        self.shift_out(self.leds_status)
    
    def turn_on_light(self, light):
        """Turn on a simple light (non-blinking)"""
        if light in ["HAZARD_LIGHTS", "LEFT_TURN", "RIGHT_TURN"]:
            return
        
        led_indices = self.LED_GROUPS.get(light, [])
        with self.lock:
            self.set_multiple_leds(led_indices, True)
            self.shift_out(self.leds_status)
    
    def turn_off_light(self, light):
        """Turn off a light and stop any effects"""
        if light == "HAZARD_LIGHTS":
            led_indices = self.LED_GROUPS["HAZARD_LIGHTS"]
        elif light == "LEFT_TURN":
            led_indices = (self.LED_GROUPS["LEFT_TURN"]["group1"] + 
                          self.LED_GROUPS["LEFT_TURN"]["group2"])
        elif light == "RIGHT_TURN":
            led_indices = (self.LED_GROUPS["RIGHT_TURN"]["group1"] + 
                          self.LED_GROUPS["RIGHT_TURN"]["group2"])
        else:
            led_indices = self.LED_GROUPS.get(light, [])
        
        with self.lock:
            self.set_multiple_leds(led_indices, False)
            self.shift_out(self.leds_status)
    
    def hazard_effect(self):
        """Blinking effect for hazard lights"""
        led_indices = self.LED_GROUPS["HAZARD_LIGHTS"]
        while self.hazard_running:
            with self.lock:
                self.set_multiple_leds(led_indices, True)
                self.shift_out(self.leds_status)
            time.sleep(0.5)
            with self.lock:
                self.set_multiple_leds(led_indices, False)
                self.shift_out(self.leds_status)
            time.sleep(0.5)
    
    def left_turn_effect(self):
        """Flowing effect for left turn signals"""
        group1 = self.LED_GROUPS["LEFT_TURN"]["group1"]
        group2 = self.LED_GROUPS["LEFT_TURN"]["group2"]
        
        while self.left_turn_running:
            with self.lock:
                # First LED in each group
                self.set_multiple_leds([group1[0], group2[0]], True)
                self.shift_out(self.leds_status)
            time.sleep(0.3)
            
            with self.lock:
                # Second LED in each group
                self.set_multiple_leds([group1[1], group2[1]], True)
                self.shift_out(self.leds_status)
            time.sleep(0.3)
            
            with self.lock:
                # Turn off first LED in each group
                self.set_multiple_leds([group1[0], group2[0]], False)
                self.shift_out(self.leds_status)
            time.sleep(0.3)
            
            with self.lock:
                # Turn off second LED in each group
                self.set_multiple_leds([group1[1], group2[1]], False)
                self.shift_out(self.leds_status)
            time.sleep(0.3)
    
    def right_turn_effect(self):
        """Flowing effect for right turn signals"""
        group1 = self.LED_GROUPS["RIGHT_TURN"]["group1"]
        group2 = self.LED_GROUPS["RIGHT_TURN"]["group2"]
        
        while self.right_turn_running:
            with self.lock:
                # First LED in each group
                self.set_multiple_leds([group1[0], group2[0]], True)
                self.shift_out(self.leds_status)
            time.sleep(0.3)
            
            with self.lock:
                # Second LED in each group
                self.set_multiple_leds([group1[1], group2[1]], True)
                self.shift_out(self.leds_status)
            time.sleep(0.3)
            
            with self.lock:
                # Turn off first LED in each group
                self.set_multiple_leds([group1[0], group2[0]], False)
                self.shift_out(self.leds_status)
            time.sleep(0.3)
            
            with self.lock:
                # Turn off second LED in each group
                self.set_multiple_leds([group1[1], group2[1]], False)
                self.shift_out(self.leds_status)
            time.sleep(0.3)
    
    def start_hazard_lights(self):
        """Start the hazard lights blinking effect"""
        self.hazard_running = True
        self.hazard_thread = threading.Thread(target=self.hazard_effect, daemon=True)
        self.hazard_thread.start()
    
    def stop_hazard_lights(self):
        """Stop the hazard lights blinking effect"""
        self.hazard_running = False
        if self.hazard_thread and self.hazard_thread.is_alive():
            self.hazard_thread.join(timeout=0.5)
        self.turn_off_light("HAZARD_LIGHTS")
    
    def start_left_turn(self):
        """Start the left turn flowing effect"""
        self.left_turn_running = True
        self.left_turn_thread = threading.Thread(target=self.left_turn_effect, daemon=True)
        self.left_turn_thread.start()
    
    def stop_left_turn(self):
        """Stop the left turn flowing effect"""
        self.left_turn_running = False
        if self.left_turn_thread and self.left_turn_thread.is_alive():
            self.left_turn_thread.join(timeout=0.5)
        self.turn_off_light("LEFT_TURN")
    
    def start_right_turn(self):
        """Start the right turn flowing effect"""
        self.right_turn_running = True
        self.right_turn_thread = threading.Thread(target=self.right_turn_effect, daemon=True)
        self.right_turn_thread.start()
    
    def stop_right_turn(self):
        """Stop the right turn flowing effect"""
        self.right_turn_running = False
        if self.right_turn_thread and self.right_turn_thread.is_alive():
            self.right_turn_thread.join(timeout=0.5)
        self.turn_off_light("RIGHT_TURN")
    
    def handle_light_command(self, light, status, mode):
        """Process received light command"""
        # Convert named signal values to strings if needed
        if hasattr(status, 'name'):
            status = status.name
        if hasattr(mode, 'name'):
            mode = mode.name
            
        # Stop any running effects first
        if light == "HAZARD_LIGHTS":
            self.stop_hazard_lights()
        elif light == "LEFT_TURN":
            self.stop_left_turn()
        elif light == "RIGHT_TURN":
            self.stop_right_turn()
        
        if status == "ACTIVATED":
            if light == "LOW_BEAM":
                # Mark that Low Beam should be on (if in correct mode)
                self.light_status[light]["should_be_on"] = True
                if mode in ["FAHREN", "WOHNEN"]:
                    self.turn_on_light("LOW_BEAM")
                    self.light_status[light]["status"] = "ACTIVATED"
            else:
                # Normal behavior for other lights
                if light == "HAZARD_LIGHTS":
                    self.start_hazard_lights()
                elif light == "LEFT_TURN":
                    self.start_left_turn()
                elif light == "RIGHT_TURN":
                    self.start_right_turn()
                else:
                    self.turn_on_light(light)
                
                self.light_status[light]["status"] = "ACTIVATED"
            
        elif status == "DEACTIVATED":
            if light == "LOW_BEAM":
                self.light_status[light]["should_be_on"] = False
            self.turn_off_light(light)
            self.light_status[light]["status"] = "DEACTIVATED"
            
        elif status in ["FAILED", "INVALID"]:
            if light == "LOW_BEAM":
                self.light_status[light]["should_be_on"] = False
            self.turn_off_light(light)
            self.light_status[light]["status"] = "DEACTIVATED"
        
        # Update mode
        self.update_mode_leds(mode)
        self.light_status[light]["mode"] = mode
        
        logging.info(f"Processed {light} command: {status} | {mode}")
    
    def send_light_response(self, light):
        """Send response for a specific light"""
        try:
            status_data = self.light_status[light]
            message = self.message_map[light]
            
            # Get raw values for status and mode
            status_value = status_data["status"]
            mode_value = status_data["mode"]
            
            # Check if the signals expect raw values or named values
            status_signal = message.get_signal_by_name(f"{light}_STATUS")
            mode_signal = message.get_signal_by_name(f"{light}_MODE")
            
            # Convert to appropriate type based on signal definition
            if status_signal.choices:
                status_value = status_data["status"]
            else:
                status_value = 1 if status_data["status"] == "ACTIVATED" else 0
                
            if mode_signal.choices:
                mode_value = status_data["mode"]
            else:
                # Mode mappings if they're not named signals
                mode_mapping = {"FAHREN": 0, "STAND": 1, "PARKING": 2, "WOHNEN": 3}
                mode_value = mode_mapping.get(status_data["mode"], 0)
            
            data = {
                f"{light}_STATUS": status_value,
                f"{light}_MODE": mode_value
            }
            
            encoded_msg = message.encode(data)
            
            msg = can.Message(
                arbitration_id=message.frame_id,
                data=encoded_msg,
                is_extended_id=False
            )
            
            self.bus.send(msg)
            logging.info(f"Sent {light} status response: {data}")
            print(f"Sent Response: {light} | {status_data['status']} | {status_data['mode']}")
            
        except Exception as e:
            logging.error(f"Failed to send {light} response: {e}")
    
    def receive_messages(self):
        """Main CAN message processing loop"""
        logging.info("Starting CAN message receiver")
        print("Listening for light control commands...")
        
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg:
                    try:
                        for light, message in self.message_map.items():
                            if msg.arbitration_id == message.frame_id:
                                data = self.db.decode_message(msg.arbitration_id, msg.data)
                                
                                # Convert named signal values to strings
                                status = data[f"{light}_STATUS"]
                                mode = data[f"{light}_MODE"]
                                
                                if hasattr(status, 'name'):
                                    status = status.name
                                if hasattr(mode, 'name'):
                                    mode = mode.name
                                
                                print(f"Received: {light} | {status} | {mode}")
                                self.handle_light_command(light, status, mode)
                                self.send_light_response(light)
                                break
                    except Exception as e:
                        logging.error(f"Message processing error: {e}")
                
        except KeyboardInterrupt:
            logging.info("Received shutdown signal")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Cleanup resources on shutdown"""
        logging.info("Initiating shutdown sequence")
        self.running = False
        
        # Stop all effects
        self.stop_hazard_lights()
        self.stop_left_turn()
        self.stop_right_turn()
        
        # Turn off all LEDs
        self.clear_register()
        
        if self.bus:
            self.bus.shutdown()
        
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        GPIO.cleanup()
        
        logging.info("Shutdown complete")
        print("Light controller stopped")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('light_slave.log'),
            logging.StreamHandler()
        ]
    )
    
    try:
        slave = CANLightSlave()
        slave.receive_messages()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        raise