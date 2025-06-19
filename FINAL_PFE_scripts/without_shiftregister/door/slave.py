import serial
import RPi.GPIO as GPIO
import time

# UART configuration
uart = serial.Serial(
    port='/dev/serial0',
    baudrate=19200,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
)

# LED GPIO pin assignments for each LIN ID
LED_PINS = {
    0x10: [4],               # ID 0x10 controls 1 LED on GPIO4
    0x23: [25, 8],           # ID 0x23 controls 2 LEDs on GPIO25 and GPIO8
    0x01: [7, 12, 16, 20],   # ID 0x01 controls 4 LEDs
    0x02: [21, 26, 19, 13],  # ID 0x02 controls 4 different LEDs
    0x03: [17, 27, 22, 10],  # ID 0x03 controls 4 different LEDs
    0x04: [9, 11, 5, 6]      # ID 0x04 controls 4 different LEDs
}

# Setup GPIO
def setup_gpio():
    GPIO.setwarnings(False)  # Suppress warnings about GPIO reinitialization
    GPIO.setmode(GPIO.BCM)
    # Setup all unique pins
    all_pins = set(pin for pins in LED_PINS.values() for pin in pins)
    for pin in all_pins:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

def parse_lin_frames(buffer):
    """Extract and validate LIN frames from the buffer."""
    frames = []
    while len(buffer) > 0:
        try:
            # Look for the sync byte (0x55)
            if buffer[0] != 0x55:
                buffer.pop(0)  # Discard invalid data
                continue

            # Check if we have enough data to read the ID
            if len(buffer) < 2:
                break

            identifier = buffer[1]

            # Determine frame length based on ID
            if identifier in [0x10, 0x11, 0x22, 0x23, 0x30]:
                frame_length = 4  # Sync + ID + Data (1 byte) + Checksum
            elif identifier in [0x01, 0x02, 0x03, 0x04]:
                frame_length = 6  # Sync + ID + Data (3 bytes) + Checksum
            else:
                buffer.pop(0)  # Discard unknown frames
                continue

            # Check if we have enough data for the full frame
            if len(buffer) < frame_length:
                break  # Wait for more data

            # Extract the frame
            frame = buffer[:frame_length]
            # Validate checksum (optional, implement if needed)
            frames.append(frame)
            buffer = buffer[frame_length:]  # Move to the next potential frame

        except IndexError:
            # If buffer is incomplete, wait for more data
            break

    return frames, buffer

def format_frame(frame):
    """Format a frame into a hex string."""
    return f"Received LIN frame in HEX: {['0x' + f'{byte:02X}'.lower() for byte in frame]}"

def control_leds(frame):
    """Control LEDs based on the received LIN frame."""
    identifier = frame[1]
    
    if identifier == 0x10:
        # ID 0x10 - single LED control
        data = frame[2]
        pin = LED_PINS[0x10][0]
        GPIO.output(pin, GPIO.HIGH if data & 0x01 else GPIO.LOW)
        
    elif identifier == 0x23:
        # ID 0x23 - flash two LEDs
        for _ in range(3):  # Flash 3 times
            for pin in LED_PINS[0x23]:
                GPIO.output(pin, GPIO.HIGH)
            time.sleep(0.2)
            for pin in LED_PINS[0x23]:
                GPIO.output(pin, GPIO.LOW)
            time.sleep(0.2)
                
    elif identifier in [0x01, 0x02, 0x03, 0x04]:
        # IDs 0x01-0x04 - control LEDs directly based on data bytes
        data_bytes = frame[2:-1]  # Get data bytes (excluding checksum)
        pins = LED_PINS[identifier]

        # Ensure that the frame structure and number of pins match
        if len(pins) >= 4:  # Verify we have at least 4 LEDs assigned
            # Process each data byte according to the rules

            # Data[0]: Controls pins 7 and 12
            if data_bytes[0] == 1:
                GPIO.output(pins[1], GPIO.HIGH)  # Turn ON pin 12
                GPIO.output(pins[0], GPIO.LOW)   # Turn OFF pin 7
            elif data_bytes[0] == 0:
                GPIO.output(pins[1], GPIO.LOW)   # Turn OFF pin 12
                GPIO.output(pins[0], GPIO.HIGH)  # Turn ON pin 7

            # Data[1]: Controls pin 16
            GPIO.output(pins[2], GPIO.HIGH if data_bytes[1] == 1 else GPIO.LOW)

            # Data[2]: Controls pin 20
            GPIO.output(pins[3], GPIO.HIGH if data_bytes[2] == 1 else GPIO.LOW)
  
def receive_and_process_frames():
    buffer = bytearray()
    setup_gpio()
    
    try:
        print("Listening for LIN frames and controlling LEDs...")
        while True:
            if uart.in_waiting:
                buffer.extend(uart.read(uart.in_waiting))
                #print(f"Raw data received (hex): {buffer.hex()}")
                frames, buffer = parse_lin_frames(buffer)
                for frame in frames:
                    print(format_frame(frame))
                    control_leds(frame)
                    
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        GPIO.cleanup()
        uart.close()

if _name_ == "_main_":
    receive_and_process_frames()