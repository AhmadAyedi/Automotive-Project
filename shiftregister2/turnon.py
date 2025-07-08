from time import sleep
import RPi.GPIO as GPIO

# Define GPIO pins
Latch = 13         # RCLK
Clock = 15         # SRCLK
Serial_Input = 11  # SER
Clear = 7          # SRCLR

NUM_LEDS = 80  # 10 shift registers

def setup():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(Clock, GPIO.OUT)
    GPIO.setup(Latch, GPIO.OUT)
    GPIO.setup(Clear, GPIO.OUT)
    GPIO.setup(Serial_Input, GPIO.OUT)

def clear_register():
    GPIO.output(Clear, 0)  # Active low
    sleep(0.01)
    GPIO.output(Clear, 1)

def shift_out(data):
    for bit in data:
        GPIO.output(Serial_Input, bit)
        GPIO.output(Clock, 0)
        GPIO.output(Clock, 1)
    GPIO.output(Latch, 0)
    GPIO.output(Latch, 1)

def turn_off_leds():
    all_off = [0] * NUM_LEDS
    shift_out(all_off)

if __name__ == "__main__":
    setup()
    clear_register()

    # Turn on all 80 LEDs
    frame = [1] * NUM_LEDS
    shift_out(frame)

    print("All 80 LEDs are ON. Press Ctrl+C to turn them OFF and exit.")
    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        print("\nTurning off all LEDs and exiting...")
        turn_off_leds()
        GPIO.cleanup()
