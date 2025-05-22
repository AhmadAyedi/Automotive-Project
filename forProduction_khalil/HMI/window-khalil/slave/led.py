import RPi.GPIO as GPIO
import time

# Use BCM pin numbering
GPIO.setmode(GPIO.BCM)

# Define LED pins
led_pins = [24, 18]

# Set up pins as outputs
for pin in led_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.HIGH)  # Turn on LED

print("LEDs on GPIO 4 and 18 are ON. Press Ctrl+C to turn them OFF and exit.")

try:
    # Keep the program running until Ctrl+C
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\nCtrl+C detected. Turning LEDs OFF...")

finally:
    # Turn off LEDs and clean up
    for pin in led_pins:
        GPIO.output(pin, GPIO.LOW)
    GPIO.cleanup()
    print("GPIO cleaned up. Exiting.")
