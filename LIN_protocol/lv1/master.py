import serial
import time
import RPi.GPIO as GPIO
from enum import Enum

# Constants
SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 19200
WAKEUP_PIN = 18

SYNC_BYTE = 0x55
BREAK_BYTE = 0x00

class FrameID(Enum):
    MOTOR_CONTROL = 0x10
    SENSOR_REQUEST = 0x11
    SENSOR_RESPONSE = 0x12

def calculate_pid(frame_id):
    if frame_id > 0x3F:
        raise ValueError("Frame ID must be 6 bits (0-63)")
    p0 = (frame_id ^ (frame_id >> 1) ^ (frame_id >> 2) ^ (frame_id >> 4)) & 0x01
    p1 = ~((frame_id >> 1) ^ (frame_id >> 3) ^ (frame_id >> 4) ^ (frame_id >> 5)) & 0x01
    return (frame_id & 0x3F) | (p0 << 6) | (p1 << 7)

def calculate_checksum(pid, data):
    checksum = pid
    for byte in data:
        checksum += byte
        if checksum > 0xFF:
            checksum -= 0xFF
    return (0xFF - checksum) & 0xFF

def send_break(ser):
    ser.baudrate = BAUD_RATE // 4
    ser.write(bytes([BREAK_BYTE]))
    ser.flush()
    time.sleep(13 * (1.0 / (BAUD_RATE // 4)))
    ser.baudrate = BAUD_RATE

def wakeup_slave():
    GPIO.output(WAKEUP_PIN, GPIO.LOW)
    time.sleep(0.01)
    GPIO.output(WAKEUP_PIN, GPIO.HIGH)

def send_frame(ser, frame_id, data=None):
    """Send a complete LIN frame"""
    wakeup_slave()
    send_break(ser)
    
    ser.write(bytes([SYNC_BYTE]))
    pid = calculate_pid(frame_id)
    ser.write(bytes([pid]))
    
    if data:
        ser.write(data)
        checksum = calculate_checksum(pid, data)
    else:
        checksum = calculate_checksum(pid, bytes())
    
    ser.write(bytes([checksum]))
    ser.flush()
    time.sleep(0.005)  # Small delay after transmission

def receive_response(ser, expected_frame_id, timeout=0.5):
    """Wait for and parse a LIN response frame"""
    start_time = time.time()
    buffer = bytes()
    
    while time.time() - start_time < timeout:
        if ser.in_waiting:
            byte = ser.read(1)
            buffer += byte
            
            # Check for break character (start of LIN frame)
            if byte == bytes([BREAK_BYTE]):
                buffer = bytes([BREAK_BYTE])  # Start fresh frame
                continue
                
            # Only proceed if we have break + sync
            if len(buffer) >= 2 and buffer[0] == BREAK_BYTE and buffer[1] == SYNC_BYTE:
                if len(buffer) >= 3:
                    pid_byte = buffer[2]
                    frame_id = pid_byte & 0x3F
                    
                    if frame_id == expected_frame_id:
                        data_length = 3  # Our sensor response is fixed at 3 bytes
                        total_length = 3 + data_length + 1  # Break+Sync+PID + data + checksum
                        
                        # Read remaining bytes if needed
                        while len(buffer) < total_length and (time.time() - start_time < timeout):
                            if ser.in_waiting:
                                buffer += ser.read(1)
                        
                        if len(buffer) >= total_length:
                            data = buffer[3:3+data_length]
                            checksum = buffer[3+data_length]
                            
                            if verify_checksum(pid_byte, data, checksum):
                                return data
        time.sleep(0.001)
    
    return None

def verify_checksum(pid, data, received_checksum):
    checksum = pid
    for byte in data:
        checksum += byte
        if checksum > 0xFF:
            checksum -= 0xFF
    checksum = (0xFF - checksum) & 0xFF
    return checksum == received_checksum

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(WAKEUP_PIN, GPIO.OUT)
    GPIO.output(WAKEUP_PIN, GPIO.HIGH)

    ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=0)

    try:
        motor_speed = 0
        direction = 1
        
        while True:
            # Send motor command
            motor_speed = (motor_speed + 10 * direction) % 100
            if motor_speed >= 100: direction = -1
            elif motor_speed <= 0: direction = 1
            
            motor_data = bytes([motor_speed, direction, 0xAA])
            print(f"\nSending motor command: speed={motor_speed}, direction={'forward' if direction == 1 else 'reverse'}")
            send_frame(ser, FrameID.MOTOR_CONTROL.value, motor_data)
            
            # Request sensor data
            print("Sending sensor data request...")
            send_frame(ser, FrameID.SENSOR_REQUEST.value)
            
            # Wait for response
            sensor_data = receive_response(ser, FrameID.SENSOR_RESPONSE.value)
            if sensor_data:
                print(f"Received sensor data: {list(sensor_data)}")
            else:
                print("No sensor response received")
            
            time.sleep(2)

    finally:
        ser.close()
        GPIO.cleanup()

if __name__ == "__main__":
    main()