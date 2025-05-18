import can
import RPi.GPIO as GPIO

# Reverse mappings for interpretation
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
    0xFF: "FAILED"
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

def setup_gpio():
    """Initialize GPIO pins for LEDs."""
    GPIO.setmode(GPIO.BCM)
    for pin in LED_PINS.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)  # Initialize LEDs to off

def control_led(light, status):
    """Control the LED based on the light type and status."""
    pin = LED_PINS.get(light)
    if pin is not None:
        if status == "activated":
            GPIO.output(pin, GPIO.HIGH)  # Turn LED on
        else:  # desactivated or FAILED
            GPIO.output(pin, GPIO.LOW)   # Turn LED off

def receive_messages():
    print("Listening for CAN messages and controlling LEDs...")
    try:
        # Setup CAN bus
        bus = can.interface.Bus(channel='can0', bustype='socketcan')
        # Setup GPIO
        setup_gpio()
        
        while True:
            msg = bus.recv(timeout=1.0)
            if msg:
                light = LIGHT_NAMES.get(msg.arbitration_id, f"Unknown ID: {hex(msg.arbitration_id)}")
                status = STATUS_NAMES.get(msg.data[0] if msg.data else 0xFF, "Unknown status")
                print(f"Received: {light} - {status}")
                
                # Control LED if light is known
                if light in LED_PINS:
                    control_led(light, status)
                else:
                    print(f"No LED control for: {light}")
                
    except KeyboardInterrupt:
        print("\nStopped listening")
    finally:
        bus.shutdown()
        GPIO.cleanup()  # Clean up GPIO resources

if __name__ == "__main__":
    receive_messages()