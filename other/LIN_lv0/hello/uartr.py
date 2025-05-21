import serial
import time

def calculate_checksum(pid, data, enhanced=True):
    total = sum(data)
    if enhanced:
        total += pid
    total &= 0xFF
    return (~total) & 0xFF

# Setup UART
ser = serial.Serial('/dev/serial0', baudrate=9600, timeout=1)
time.sleep(2)

def read_lin_frame():
    # Wait for SYNC
    while True:
        byte = ser.read(1)
        if not byte:
            continue
        if byte[0] == 0x55:
            print("SYNC received")
            break

    # Read PID
    pid_bytes = ser.read(1)
    if not pid_bytes:
        print("Failed to read PID")
        return
    pid = pid_bytes[0]

    # Read Data + Checksum (we expect 5 data bytes for "Hello")
    frame = ser.read(6)  # 5 data + 1 checksum
    if len(frame) < 6:
        print("Incomplete frame")
        return

    data = list(frame[:-1])
    checksum = frame[-1]
    expected = calculate_checksum(pid, data)

    valid = (checksum == expected)
    message = ''.join(chr(b) for b in data if 32 <= b <= 126)

    print(f"Received: PID=0x{pid:02X}, Data={data} ('{message}'), Checksum=0x{checksum:02X} [Valid: {valid}]")

print("Waiting for LIN frames... Press Ctrl+C to stop.\n")
try:
    while True:
        read_lin_frame()
except KeyboardInterrupt:
    ser.close()
    print("\nStopped listening.")
