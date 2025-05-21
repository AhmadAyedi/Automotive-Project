import serial
import time

def calculate_pid(id_byte):
    id_bits = id_byte & 0x3F
    p0 = ((id_bits >> 0) ^ (id_bits >> 1) ^ (id_bits >> 2) ^ (id_bits >> 4)) & 0x01
    p1 = (~((id_bits >> 1) ^ (id_bits >> 3) ^ (id_bits >> 4) ^ (id_bits >> 5))) & 0x01
    pid = id_bits | (p0 << 6) | (p1 << 7)
    return pid

def calculate_checksum(pid, data, enhanced=True):
    total = sum(data)
    if enhanced:
        total += pid
    total &= 0xFF
    return (~total) & 0xFF

def send_lin_frame(ser, id_byte, data):
    # --- Send break: 13+ bits low (dominant) ---
    ser.break_condition = True
    time.sleep(0.0015)  # 13+ bits at 9600 baud = 1.35ms min
    ser.break_condition = False
    time.sleep(0.001)   # Inter-byte space

    # --- Send Sync ---
    ser.write(bytes([0x55]))

    # --- Send PID ---
    pid = calculate_pid(id_byte)
    ser.write(bytes([pid]))

    # --- Send Data ---
    ser.write(bytes(data))

    # --- Send Checksum ---
    checksum = calculate_checksum(pid, data)
    ser.write(bytes([checksum]))

    print(f"Sent LIN Frame -> PID: 0x{pid:02X}, Data: {data}, Checksum: 0x{checksum:02X}")

# Setup UART
ser = serial.Serial('/dev/serial0', baudrate=9600, timeout=1)
time.sleep(2)

# Send frame in a loop
message = "Hello"
data = [ord(c) for c in message]
id_byte = 0x12  # LIN ID for this frame

try:
    while True:
        send_lin_frame(ser, id_byte, data)
        time.sleep(2)
except KeyboardInterrupt:
    ser.close()
    print("\nStopped sending LIN frames.")
