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

def send_break(ser):
    ser.baudrate = BAUD_RATE // 4
    ser.write(bytes([BREAK_BYTE]))
    ser.flush()
    time.sleep(13 * (1.0 / (BAUD_RATE // 4)))
    ser.baudrate = BAUD_RATE

def verify_checksum(pid, data, received_checksum):
    checksum = pid
    for byte in data:
        checksum += byte
        if checksum > 0xFF:
            checksum -= 0xFF
    checksum = (0xFF - checksum) & 0xFF
    return checksum == received_checksum

def parse_pid(pid_byte):
    frame_id = pid_byte & 0x3F
    p0 = (pid_byte >> 6) & 0x01
    p1 = (pid_byte >> 7) & 0x01
    calc_p0 = (frame_id ^ (frame_id >> 1) ^ (frame_id >> 2) ^ (frame_id >> 4)) & 0x01
    calc_p1 = ~((frame_id >> 1) ^ (frame_id >> 3) ^ (frame_id >> 4) ^ (frame_id >> 5)) & 0x01
    if p0 != calc_p0 or p1 != calc_p1:
        return None
    return frame_id

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

def send_lin_response(ser, frame_id, data):
    """Send a complete LIN response frame (with break and sync)"""
    send_break(ser)
    ser.write(bytes([SYNC_BYTE]))
    pid = calculate_pid(frame_id)
    ser.write(bytes([pid]))
    ser.write(data)
    checksum = calculate_checksum(pid, data)
    ser.write(bytes([checksum]))
    ser.flush()
    time.sleep(0.005)

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(WAKEUP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=0.1)
    sensor_values = [0x25, 0x40, 0x7F]

    try:
        print("LIN Slave Node - Listening for frames...")
        while True:
            if ser.in_waiting:
                byte = ser.read(1)
                if byte == bytes([BREAK_BYTE]):
                    try:
                        sync = ser.read(1)
                        if sync != bytes([SYNC_BYTE]):
                            continue

                        pid_byte = ord(ser.read(1))
                        frame_id = parse_pid(pid_byte)
                        if frame_id is None:
                            continue

                        if frame_id == FrameID.MOTOR_CONTROL.value:
                            data = ser.read(3)
                            if len(data) != 3:
                                continue

                            checksum = ord(ser.read(1))
                            if not verify_checksum(pid_byte, data, checksum):
                                continue

                            speed = data[0]
                            direction = data[1]
                            print(f"\nMotor command received - Speed: {speed}, Direction: {'forward' if direction == 1 else 'reverse'}")

                        elif frame_id == FrameID.SENSOR_REQUEST.value:
                            checksum = ord(ser.read(1))
                            if not verify_checksum(pid_byte, bytes(), checksum):
                                continue

                            print("Sensor data requested, sending response...")
                            # Update sensor values
                            sensor_values[0] = (sensor_values[0] + 1) % 256
                            sensor_values[1] = (sensor_values[1] + 2) % 256
                            sensor_values[2] = (sensor_values[2] + 3) % 256
                            
                            time.sleep(0.002)  # Inter-frame spacing
                            send_lin_response(ser, FrameID.SENSOR_RESPONSE.value, bytes(sensor_values))

                    except Exception as e:
                        print(f"Error: {e}")
                        continue

    finally:
        ser.close()
        GPIO.cleanup()

if __name__ == "__main__":
    main()