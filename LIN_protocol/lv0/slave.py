import serial
import time
import RPi.GPIO as GPIO

# Constants
SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 19200
WAKEUP_PIN = 18

SYNC_BYTE = 0x55
BREAK_BYTE = 0x00

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

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(WAKEUP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=0.1)

    try:
        print("Listening for LIN frames...")
        while True:
            if ser.in_waiting:
                byte = ser.read(1)
                if byte == bytes([BREAK_BYTE]):
                    try:
                        sync = ser.read(1)
                        if sync != bytes([SYNC_BYTE]):
                            print("Invalid sync byte")
                            continue

                        pid_byte = ord(ser.read(1))
                        frame_id = parse_pid(pid_byte)
                        if frame_id is None:
                            print("PID parity check failed")
                            continue

                        data = ser.read(3)
                        if len(data) != 3:
                            print(f"Incomplete data: got {len(data)} bytes")
                            continue

                        checksum = ord(ser.read(1))
                        if not verify_checksum(pid_byte, data, checksum):
                            print("Checksum mismatch")
                            continue

                        print(f"Received Frame ID: {frame_id}, Data: {list(data)}")

                    except Exception as e:
                        print(f"Error receiving frame: {e}")
                        continue

    finally:
        ser.close()
        GPIO.cleanup()

if __name__ == "__main__":
    main()
