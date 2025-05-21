import RPi.GPIO as GPIO
import time

# List of GPIO pins connected to LEDs
led_pins = [2, 3, 15, 17, 27, 22, 0, 5, 6, 13, 19, 26, 12, 16, 20, 21]

# Use BCM pin numbering
GPIO.setmode(GPIO.BCM)

# Set all pins as outputs and turn them ON
for pin in led_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.HIGH)  # Use GPIO.LOW if active-low LEDs

print("All LEDs are ON. Press Ctrl+C to turn them OFF.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nTurning off all LEDs...")
    for pin in led_pins:
        GPIO.output(pin, GPIO.LOW)  # Use GPIO.HIGH if active-low LEDs
    GPIO.cleanup()
    print("Cleanup done. Exiting.")
