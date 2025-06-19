# author: Heni Elloumi 
# you can contact me via my email: henii.elloumi@gmail.com
"""
To undrestand the code below we need to undrestand
how the 74HC595 shift register work.

                     | | | | | | | |
                    ++-+-+-+-+-+-+-++
                    |               |
                    |   74HC595    ++
                    |              ++
                    |               |
                    ++-+-+-+-+-+-+-++
                     | | | | | | | |

To undrestand that, click the link below
https://lastminuteengineers.com/74hc595-shift-register-arduino-tutorial/

For more information you can download the Datasheet by going to the link below
https://www.ti.com/lit/ds/symlink/sn74hc595.pdf
"""
# Note:
""" our shift register is 40-bit register formed by daisy-chaining* five 8-bit register 

# daisy-chaining*: to link (things, such as computer components) together in series """

# import the nessecery library
from time import sleep # imports the sleep function from the time module
import RPi.GPIO as GPIO # imports the RPi.GPIO module to use the functions associated with it

# Define Connections to 74HC595
Latch = 13 # sets the RCLK (Register Clock / Latch) to the GPIO pin 15
Clock = 15 # sets the SRCLK (Shift Register Clock) to the GPIO pin 13
Serial_Input = 11 # sets the Serial_Input to the GPIO pin 11
Clear = 7 # sets the Shift Register Clear to the GPIO pin 7
# Note:
# We cannot change the pins number as this is how they were 
# configured on the connector board made by Primatec. 

# initialize the leds status as turned off
# by creating a list of 40 elements containing zeros
LEDs_status = [0] * 40

# setup gpio config
def setup():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(Clock, GPIO.OUT)
    GPIO.setup(Latch, GPIO.OUT)
    GPIO.setup(Clear, GPIO.OUT)
    GPIO.setup(Serial_Input, GPIO.OUT)

# various functions to Dislay the LEDs in a different way 
def Display1():
    """
    this function turn on the LEDs, one at a time
    """
    global Latch, Serial_Input, Clock, Clear, LEDs_status

    # Clear the Shift Register (Reset) by pulling the Clear to low
    GPIO.output(Clear, 0)
    GPIO.output(Clear, 1)

    print('turning on the LEDs, one at a time')
    for i in range(40):
        print(f'led number "{i}" is turned on')
        LEDs_status[i] = 1

        # iterate through the list of the LEDs_status 
        # to push them in the shift register 
        for state in LEDs_status:
            GPIO.output(Serial_Input, state)
            # each loop generate a clock signal 
            # to shift the Serial input in the shift register
            GPIO.output(Clock, 0)
            GPIO.output(Clock, 1)

        # after pushing all the LEDs_status in the shift register
        # trigger the Latch to High to output the contents of 
        # the shift register
        # meannig, to turn the LEDs ON/OFF according to their status 
        # in the LEDs_status list
        GPIO.output(Latch, 0)
        GPIO.output(Latch, 1)

        # Wait for 5 second
        sleep(1)

        # turn OFF the LED that has been lit by making thier status 0 
        # and then go to light the next led
        LEDs_status = [0] * 40
        # or
        # LEDs_status[i] = 0

def Display2():
    """
    this function turn on the LEDs in sequence while keeping the previously lit
    """
    global Latch, Serial_Input, Clock, Clear, LEDs_status
    
    # Clear the Shift Register outputs(Reset) by pulling the Clear to low
    GPIO.output(Clear, 0)
    GPIO.output(Clear, 1)

    print('Sequentially turning on the LEDs')
    for i in range(40):
        print(f'turning led number: {i} ON')
        LEDs_status[i] = 1

        for state in LEDs_status:
            GPIO.output(Serial_Input, state)
            # each loop generate a clock signal 
            # to shift the Serial input in the shift register
            GPIO.output(Clock, 0)
            GPIO.output(Clock, 1)

        # turn the LEDs
        GPIO.output(Latch, 0)
        GPIO.output(Latch, 1)
        sleep(0.1)

        # we can see here we didn't turn OFF the LED that 
        # has been lit like Display1 function above 


def Display3():
    """
    After all the LEDs have been sequentially lit, this function turns off each LED in reverse order, one by one.
    """
    global Latch, Serial_Input, Clock, Clear, LEDs_status
    
    # Clear the Shift Register outputs(Reset) by pulling the Clear to low
    GPIO.output(Clear, 0)
    GPIO.output(Clear, 1)
    
    print('Sequentially turning off the LEDs in reverse order')
    for i in range(39,-1,-1):
        print(f'led number "{i}" is turned off')
        LEDs_status[i] = 0

        for state in LEDs_status:
            GPIO.output(Serial_Input, state)
            # each loop generate a clock signal 
            # to shift the Serial input in the shift register
            GPIO.output(Clock, 0)
            GPIO.output(Clock, 1)
        
        # turn the LEDs
        GPIO.output(Latch, 0)
        GPIO.output(Latch, 1)
        sleep(0.1)

""" Here is the beginning of the main code """
# setup gpio config
setup()
# Sequentially turning on the LEDs
#Display1()
while True:

    # Sequentially turning on the LEDs
    Display2()
    # Sequentially turning off the LEDs in reverse order
    Display3()

