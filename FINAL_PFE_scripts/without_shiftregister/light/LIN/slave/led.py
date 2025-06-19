import RPi.GPIO as GPIO
import time
import signal
import sys

# List of GPIO pins
pins = [18, 24, 7]

# Setup
GPIO.setmode(GPIO.BCM)
for pin in pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.HIGH)  # Activate (HIGH = ON)

print("GPIOs activated. Press Ctrl+C to deactivate and exit.")

# Signal handler for Ctrl+C
def cleanup(signum, frame):
    print("\nDeactivating GPIOs and cleaning up...")
    for pin in pins:
        GPIO.output(pin, GPIO.LOW)  # Deactivate (LOW = OFF)
    GPIO.cleanup()
    sys.exit(0)

# Register the signal handler
signal.signal(signal.SIGINT, cleanup)

# Keep the program running
while True:
    time.sleep(1)
