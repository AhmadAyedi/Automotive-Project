import can
import time
import os

# CAN IDs for each light type
LIGHT_IDS = {
    "Low Beam": 0x101,
    "High Beam": 0x102,
    "Parking Left": 0x103,
    "Parking Right": 0x104,
    "Hazard Lights": 0x105,
    "Right Turn": 0x106,
    "Left Turn": 0x107
}

# Status codes (1 byte)
STATUS_CODES = {
    "activated": 0x01,
    "desactivated": 0x00,
    "FAILED": 0xFF
}

def send_can_message(light, status):
    try:
        bus = can.interface.Bus(channel='can0', bustype='socketcan')
        msg = can.Message(
            arbitration_id=LIGHT_IDS[light],
            data=[STATUS_CODES[status]],
            is_extended_id=False
        )
        bus.send(msg)
        print(f"Sent: {light} - {status} (ID: {hex(LIGHT_IDS[light])}, Data: {hex(STATUS_CODES[status])})")
        bus.shutdown()
    except Exception as e:
        print(f"Error sending CAN message: {e}")

def monitor_file(filename):
    print(f"Monitoring {filename} for new light status updates...")
    print("Add new lines to the file to send CAN messages")
    
    # Get initial file size
    last_size = os.path.getsize(filename)
    
    try:
        while True:
            current_size = os.path.getsize(filename)
            
            # Only check if file has grown
            if current_size > last_size:
                with open(filename, 'r') as f:
                    # Read just the new portion
                    f.seek(last_size)
                    new_content = f.read()
                    last_size = current_size
                    
                    # Process all new lines
                    lines = new_content.split('\n')
                    for line in lines:
                        if line.strip() and line.startswith("Light:") and "Result:" in line:
                            try:
                                parts = line.split('|')
                                light = parts[0].split(':')[1].strip()
                                status = parts[1].split(':')[1].strip()
                                
                                if light in LIGHT_IDS and status in STATUS_CODES:
                                    send_can_message(light, status)
                                else:
                                    print(f"Ignoring unknown light/status: {line}")
                            except IndexError:
                                print(f"Malformed line: {line}")
            
            time.sleep(0.1)  # Check 10 times per second
            
    except KeyboardInterrupt:
        print("\nStopped monitoring")

if __name__ == "__main__":
    monitor_file("analysis_results.txt")