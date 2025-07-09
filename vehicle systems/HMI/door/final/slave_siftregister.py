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

# Shift register output mapping (GPIO to shift register output)
GPIO_TO_SHIFT = {
    4: 41,
    25: 42,
    8: 43,
    7: 44,
    12: 45,
    16: 46,
    20: 47,
    21: 48,
    26: 49,
    19: 50,
    13: 51,
    17: 52,
    27: 53,
    22: 54,
    10: 55,
    9: 56,
    11: 57,
    5: 58,
    6: 59
}

# LED assignments (now using shift register outputs)
LED_PINS = {
    0x10: [41],               # ID 0x10 controls output 41
    0x23: [42, 43],           # ID 0x23 controls outputs 42-43
    0x01: [44, 45, 46, 47],  # ID 0x01 controls 4 outputs
    0x02: [48, 49, 50, 51],  # ID 0x02 controls 4 outputs
    0x03: [52, 53, 54, 55],  # ID 0x03 controls 4 outputs
    0x04: [56, 57, 58, 59]   # ID 0x04 controls 4 outputs
}

# Shift register control pins (using BOARD numbering)
SHIFT_REGISTER_PINS = {
    'Latch': 13,    # GPIO27 (pin 13 on BOARD mode)
    'Clock': 15,    # GPIO22
    'Data': 11,     # GPIO17
    'Clear': 7      # GPIO4
}

# Global state for all 80 possible shift register outputs
shift_register_state = [0] * 80

def setup_shift_register():
    """Initialize GPIO and shift register"""
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    
    # Setup shift register control pins
    for pin_name, pin_num in SHIFT_REGISTER_PINS.items():
        GPIO.setup(pin_num, GPIO.OUT)
        GPIO.output(pin_num, GPIO.LOW)
    
    # Initialize shift register (clear all outputs)
    GPIO.output(SHIFT_REGISTER_PINS['Clear'], 0)
    GPIO.output(SHIFT_REGISTER_PINS['Clear'], 1)
    update_shift_register()

def update_shift_register():
    """Update the physical shift registers with current state"""
    # Latch pin low while shifting data
    GPIO.output(SHIFT_REGISTER_PINS['Latch'], 0)
    
    # Shift out data (LSB first for cascaded registers)
    for i in range(79, -1, -1):
        GPIO.output(SHIFT_REGISTER_PINS['Data'], shift_register_state[i])
        # Pulse clock
        GPIO.output(SHIFT_REGISTER_PINS['Clock'], 1)
        GPIO.output(SHIFT_REGISTER_PINS['Clock'], 0)
    
    # Latch the data to outputs
    GPIO.output(SHIFT_REGISTER_PINS['Latch'], 1)

def set_shift_output(output_num, state):
    """Set a specific shift register output"""
    if 0 <= output_num < 80:
        shift_register_state[output_num] = 1 if state else 0
        update_shift_register()

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
            frames.append(frame)
            buffer = buffer[frame_length:]  # Move to next potential frame

        except IndexError:
            break

    return frames, buffer

def format_frame(frame):
    """Format a frame into a hex string."""
    return f"Received LIN frame in HEX: {['0x' + f'{byte:02X}'.lower() for byte in frame]}"

def control_leds(frame):
    """Control shift register outputs based on LIN frame (same logic as GPIO version)"""
    identifier = frame[1]
    
    if identifier == 0x10:
        # ID 0x10 - single output control (output 41)
        data = frame[2]
        set_shift_output(41, data & 0x01)
        
    elif identifier == 0x23:
        # ID 0x23 - flash two outputs (42-43)
        for _ in range(3):
            set_shift_output(42, 1)
            set_shift_output(43, 1)
            time.sleep(0.2)
            set_shift_output(42, 0)
            set_shift_output(43, 0)
            time.sleep(0.2)
                
    elif identifier in [0x01, 0x02, 0x03, 0x04]:
        # IDs 0x01-0x04 - control outputs based on data bytes
        data_bytes = frame[2:-1]  # Get data bytes (excluding checksum)
        pins = LED_PINS[identifier]

        if len(pins) >= 4:
            # Data[0]: Controls outputs 44 and 45 (originally GPIO7 and GPIO12)
            if data_bytes[0] == 1:
                set_shift_output(pins[1], 1)  # Output 45 ON
                set_shift_output(pins[0], 0)  # Output 44 OFF
            elif data_bytes[0] == 0:
                set_shift_output(pins[1], 0)  # Output 45 OFF
                set_shift_output(pins[0], 1)  # Output 44 ON

            # Data[1]: Controls output 46 (originally GPIO16)
            set_shift_output(pins[2], data_bytes[1] == 1)

            # Data[2]: Controls output 47 (originally GPIO20)
            set_shift_output(pins[3], data_bytes[2] == 1)

def receive_and_process_frames():
    buffer = bytearray()
    setup_shift_register()
    
    try:
        print("Listening for LIN frames and controlling shift register outputs...")
        while True:
            if uart.in_waiting:
                buffer.extend(uart.read(uart.in_waiting))
                frames, buffer = parse_lin_frames(buffer)
                for frame in frames:
                    print(format_frame(frame))
                    control_leds(frame)
                    
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Clear all outputs on exit
        for i in range(80):
            shift_register_state[i] = 0
        update_shift_register()
        GPIO.cleanup()
        uart.close()

if __name__ == "__main__":
    receive_and_process_frames()