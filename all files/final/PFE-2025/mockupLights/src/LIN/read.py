import time
import serial

# UART configuration for LIN communication
uart = serial.Serial(
    port='/dev/serial0',  # Update with the UART port on your Raspberry Pi
    baudrate=19200,       # LIN baudrate (common setting)
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
)

# Light Identifiers
LIGHT_IDS = {
    "low_beam": 0x01,
    "hazard": 0x02,
    "left_turn": 0x03,
    "right_turn": 0x04,
    "high_beam": 0x05,
    "parking_right": 0x06,
    "parking_left": 0x07
}

# Function to calculate checksum (standard LIN checksum)
def calculate_checksum(identifier, data_bytes):
    return (~(sum(data_bytes) + identifier) & 0xFF)

# Function to create a LIN frame
def create_lin_frame(identifier, data_bytes):
    sync_field = 0x55  # Sync field for LIN communication
    checksum = calculate_checksum(identifier, data_bytes)
    frame = [0x00, sync_field, identifier] + data_bytes + [checksum]
    return frame

# Function to send LIN frame in hexadecimal format
def send_lin_frame(frame):
    hex_frame = [hex(byte) for byte in frame]
    uart.write(bytes(frame))  # Send the LIN frame via UART
    print(f"Sent LIN frame in HEX: {hex_frame}")

# Function to process new lines from the file
def process_new_lines(lines):
    for line in lines:
        # Check if the line contains a light result
        if "Light:" in line and "Result:" in line:
            # Extract the light name and status
            parts = line.split("|")
            light_part = parts[0].strip()  # e.g., "Light: Hazard Lights"
            result_part = parts[1].strip()  # e.g., "Result: PASSED (deactivated)"

            # Get the light name and status
            light = light_part.split(":")[1].strip()  # Extracts "Hazard Lights"
            status = result_part.split(":")[1].strip()  # Extracts "PASSED (deactivated)" or "FAILED"

            # Check if the light matches any in the LIGHT_IDS dictionary
            for key, id_value in LIGHT_IDS.items():
                if key.replace("_", " ").lower() in light.lower():
                    # Encode status into data bytes
                    data_bytes = [ord(char) for char in status[:8]]  # Encode status as ASCII
                    data_bytes = data_bytes[:8]  # Ensure max 8 bytes
                    
                    # Generate and send LIN frame
                    lin_frame = create_lin_frame(id_value, data_bytes)
                    send_lin_frame(lin_frame)
                    print(f"Light: {light}, Status: {status}")
                    break
            else:
                print(f"Unknown light: {light}")

# Monitor the file for updates
def tail_file(file_path):
    with open(file_path, 'r') as file:
        # Move to the end of the file
        file.seek(0, 2)
        while True:
            lines = file.readlines()
            if lines:
                process_new_lines(lines)
            time.sleep(0.5)

if __name__ == "__main__":
    file_path = '/home/pi/vsomeip/PFE-2025/mockupLights/src/analysis_results.txt'  # Path to the file
    print("Monitoring file for updates and sending LIN frames...")
    tail_file(file_path)
