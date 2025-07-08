
from time import sleep
import RPi.GPIO as GPIO

# Define Connections to 74HC595
Latch = 13
Clock = 15
Serial_Input = 11
Clear = 7

# LED status list (all ON or all OFF)
LEDs_on = [1] * 40
LEDs_off = [0] * 40

def setup():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(Clock, GPIO.OUT)
    GPIO.setup(Latch, GPIO.OUT)
    GPIO.setup(Clear, GPIO.OUT)
    GPIO.setup(Serial_Input, GPIO.OUT)

def shift_out(data):
    for state in data:
        GPIO.output(Serial_Input, state)
        GPIO.output(Clock, 0)
        GPIO.output(Clock, 1)
    GPIO.output(Latch, 0)
    GPIO.output(Latch, 1)

def clear_register():
    GPIO.output(Clear, 0)
    GPIO.output(Clear, 1)

def turn_off_leds():
    shift_out(LEDs_off)
    print("All LEDs turned OFF")

if __name__ == "__main__":
    setup()
    clear_register()

    print("Blinking all 40 LEDs... (Ctrl+C to stop)")
    try:
        while True:
            shift_out(LEDs_on)
            sleep(1.5)
            shift_out(LEDs_off)
            sleep(1.5)
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Turning OFF all LEDs...")
        turn_off_leds()
        GPIO.cleanup()