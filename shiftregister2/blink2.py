from time import sleep
import RPi.GPIO as GPIO

# Define Connections to first 74HC595 in the chain
LATCH = 13
CLOCK = 15
SERIAL_INPUT = 11
CLEAR = 7

# LED status lists (now for 80 LEDs)
LEDs_on = [1] * 80
LEDs_off = [0] * 80

def setup():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(CLOCK, GPIO.OUT)
    GPIO.setup(LATCH, GPIO.OUT)
    GPIO.setup(CLEAR, GPIO.OUT)
    GPIO.setup(SERIAL_INPUT, GPIO.OUT)
    
    # Initialize all pins to low
    GPIO.output(CLOCK, 0)
    GPIO.output(LATCH, 0)
    GPIO.output(SERIAL_INPUT, 0)
    GPIO.output(CLEAR, 1)  # Active low, so 1 means not clearing

def shift_out(data):
    # Send data to the shift register chain
    for state in reversed(data):  # Send MSB first (last LED in chain)
        GPIO.output(SERIAL_INPUT, state)
        # Pulse clock
        GPIO.output(CLOCK, 1)
        GPIO.output(CLOCK, 0)
    
    # Latch the data to output registers
    GPIO.output(LATCH, 1)
    GPIO.output(LATCH, 0)

def clear_register():
    GPIO.output(CLEAR, 0)  # Active low clear
    GPIO.output(CLEAR, 1)  # Return to normal operation

def turn_off_leds():
    shift_out(LEDs_off)
    print("All 80 LEDs turned OFF")

if __name__ == "__main__":
    setup()
    clear_register()

    print("Blinking all 80 LEDs... (Ctrl+C to stop)")
    try:
        while True:
            shift_out(LEDs_on)
            sleep(0.5)
            shift_out(LEDs_off)
            sleep(0.5)
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Turning OFF all LEDs...")
        turn_off_leds()
        GPIO.cleanup()