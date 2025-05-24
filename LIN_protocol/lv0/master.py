import serial
import time
import RPi.GPIO as GPIO

# Constants
SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 19200
WAKEUP_PIN = 18

SYNC_BYTE = 0x55
BREAK_BYTE = 0x00
MAX_FRAME_DATA_LENGTH = 8

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

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(WAKEUP_PIN, GPIO.OUT)
    GPIO.output(WAKEUP_PIN, GPIO.HIGH)

    ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=0)

    try:
        frame_id = 0x12
        counter = 0

        while True:
            data = bytes([counter % 256, (counter + 1) % 256, (counter + 2) % 256])

            wakeup_slave()
            send_break(ser)

            ser.write(bytes([SYNC_BYTE]))
            pid = calculate_pid(frame_id)
            ser.write(bytes([pid]))
            ser.write(data)
            checksum = calculate_checksum(pid, data)
            ser.write(bytes([checksum]))
            ser.flush()

            print(f"Sent frame #{counter}: ID=0x{frame_id:02X}, Data={list(data)}")
            counter += 1
            time.sleep(1)  # send every 1 second

    finally:
        ser.close()
        GPIO.cleanup()

if __name__ == "__main__":
    main()
