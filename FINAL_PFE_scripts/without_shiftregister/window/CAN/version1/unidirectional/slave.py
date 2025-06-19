import can
import RPi.GPIO as GPIO
import time
from collections import defaultdict

# Reverse mappings for interpretation
WINDOW_NAMES = {
    0x201: "DR",
    0x202: "PS",
    0x203: "DRS",
    0x204: "PRS"
}

# GPIO pins for each window's LEDs
WINDOW_LEDS = {
    "DR": [2, 3, 15, 17],    # DR window LEDs
    "PS": [27, 22, 0, 5],    # PS window LEDs
    "DRS": [6, 13, 19, 26],  # DRS window LEDs
    "PRS": [12, 16, 20, 21]  # PRS window LEDs
}

# Track current state of each window (0-4 LEDs on)
current_led_states = defaultdict(int)

def setup_gpio():
    """Initialize GPIO pins for all window LEDs."""
    GPIO.setmode(GPIO.BCM)
    for leds in WINDOW_LEDS.values():
        for pin in leds:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)  # Initialize all LEDs to off

def get_required_leds(level):
    """Determine how many LEDs should be on based on the level."""
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

def update_window_leds(window, new_level):
    """Update the LEDs for a window based on the new level."""
    required_leds = get_required_leds(new_level)
    current_leds = current_led_states[window]
    leds = WINDOW_LEDS[window]
    
    print(f"Updating {window} from {current_leds} LEDs to {required_leds} LEDs (Level: {new_level}%)")
    
    # If we need to turn on more LEDs
    if required_leds > current_leds:
        for i in range(current_leds, required_leds):
            GPIO.output(leds[i], GPIO.HIGH)
            print(f"Turned on {window} LED {i+1} (GPIO {leds[i]})")
            time.sleep(1)
    
    # If we need to turn off LEDs
    elif required_leds < current_leds:
        for i in range(current_leds-1, required_leds-1, -1):
            GPIO.output(leds[i], GPIO.LOW)
            print(f"Turned off {window} LED {i+1} (GPIO {leds[i]})")
            time.sleep(1)
    
    # Update current state
    current_led_states[window] = required_leds

def receive_messages():
    print("Listening for CAN messages and controlling window LEDs...")
    try:
        # Setup CAN bus
        bus = can.interface.Bus(channel='can0', bustype='socketcan')
        # Setup GPIO
        setup_gpio()
        
        while True:
            msg = bus.recv(timeout=1.0)
            if msg:
                window = WINDOW_NAMES.get(msg.arbitration_id, f"Unknown ID: {hex(msg.arbitration_id)}")
                level = msg.data[0] if msg.data else 0
                
                if window in WINDOW_LEDS and 0 <= level <= 100:
                    print(f"Received: {window} - Level: {level}%")
                    update_window_leds(window, level)
                else:
                    print(f"Ignoring unknown window or invalid level: {window} - {level}")
                
    except KeyboardInterrupt:
        print("\nStopped listening")
    finally:
        bus.shutdown()
        GPIO.cleanup()  # Clean up GPIO resources

if __name__ == "__main__":
    receive_messages()